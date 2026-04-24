import json
from pathlib import Path

import requests

from .auth import AuthError, build_auth_headers, handle_auth_error, mask_token
from .config import AppConfig

TASKS_PATH = "/v1/user-service/my/tasks"
DEFAULT_PAGE_LIMIT = 500


class NetworkError(Exception):
    pass


class RateLimitError(Exception):
    pass


class EmptyResultError(Exception):
    pass


class PaginationStrategy:
    @staticmethod
    def extract_next_cursor(response: dict, hits: list[dict]) -> str | None:
        for key in ("nextCursor", "cursor"):
            val = response.get(key)
            if val:
                return str(val)
        if hits:
            last_id = hits[-1].get("id")
            if last_id is not None:
                return str(last_id)
        return None


class BambuCloudClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._session = requests.Session()
        self._session.headers.update(build_auth_headers(config.access_token))
        self._raw_pages: list[dict] = []

    def fetch_all_tasks(self) -> list[dict]:
        all_hits: list[dict] = []
        self._raw_pages = []
        after: str | None = None
        page_num = 1
        seen_cursors: set[str] = set()

        while True:
            print(f"[INFO] 正在取得第 {page_num} 頁...")
            response = self._fetch_page(after=after)
            self._raw_pages.append(response)

            total: int = response.get("total", 0)
            hits: list[dict] = response.get("hits") or []

            if not hits:
                if not all_hits:
                    raise EmptyResultError("列印歷史為空，目前帳號無任何列印紀錄。")
                if len(all_hits) < total:
                    print(
                        f"[WARN] 資料可能不完整：API 回傳空頁，"
                        f"但 total={total} 尚有 {total - len(all_hits)} 筆未取得。"
                    )
                break

            all_hits.extend(hits)
            print(f"[INFO] 已取得 {len(all_hits)} / {total} 筆")

            if len(all_hits) >= total:
                break

            next_cursor = PaginationStrategy.extract_next_cursor(response, hits)
            if not next_cursor:
                print("[WARN] 無法取得下一頁游標，停止分頁。")
                break

            if next_cursor in seen_cursors:
                print("[WARN] 偵測到重複游標，停止分頁以防無限迴圈。")
                break
            seen_cursors.add(next_cursor)

            after = next_cursor
            page_num += 1

        return all_hits

    def _fetch_page(self, after: str | None = None) -> dict:
        url = self._config.api_base + TASKS_PATH
        params: dict = {"limit": DEFAULT_PAGE_LIMIT}
        if after is not None:
            params["after"] = after

        try:
            resp = self._session.get(
                url,
                params=params,
                timeout=self._config.request_timeout,
            )
        except requests.Timeout:
            raise NetworkError(
                f"[ERROR] 連線逾時（{self._config.request_timeout} 秒）。"
                " 請確認網路連線是否正常。"
            )
        except requests.ConnectionError as exc:
            raise NetworkError(f"[ERROR] 網路連線失敗：{exc}") from exc
        except requests.RequestException as exc:
            raise NetworkError(f"[ERROR] 請求發生非預期錯誤：{exc}") from exc

        if resp.status_code in (401, 403):
            handle_auth_error(resp.status_code, mask_token(self._config.access_token))

        if resp.status_code == 429:
            raise RateLimitError(
                "[ERROR] 請求次數過多（HTTP 429）。請稍後再試。"
            )

        if not resp.ok:
            raise NetworkError(
                f"[ERROR] API 回傳非預期狀態碼：{resp.status_code}。"
                f" 回應內容：{resp.text[:200]}"
            )

        try:
            return resp.json()
        except ValueError as exc:
            raise NetworkError(
                f"[ERROR] API 回傳非 JSON 格式的回應：{resp.text[:200]}"
            ) from exc

    def save_raw_tasks(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        total_fetched = sum(len(p.get("hits") or []) for p in self._raw_pages)
        payload = {
            "total_fetched": total_fetched,
            "pages": self._raw_pages,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[OK] Raw 資料已儲存：{output_path}")
