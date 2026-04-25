import json
from pathlib import Path

from .config import AppConfig
from .db import (
    get_connection,
    get_db_path,
    insert_print_task_filament,
    insert_print_task_ignore,
    upsert_printer,
)


class IngestionError(Exception):
    pass


def _extract_slot_id(item: dict) -> int | None:
    # slotId 優先（真實 Bambu API），position 為 fallback（sample/測試資料）
    for key in ("slotId", "position"):
        val = item.get(key)
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                continue
    return None


def _convert_color(raw_color: str | None) -> str | None:
    if not raw_color or len(raw_color) != 8:
        return None
    try:
        int(raw_color, 16)
        return f"#{raw_color[:6].upper()}"
    except ValueError:
        return None


def _extract_print_name(raw: dict) -> str | None:
    for key in ("title", "design_title", "name"):
        val = raw.get(key)
        if val:
            return str(val)
    return None


def _build_filament_rows(raw_task: dict, print_task_id: int) -> list[dict]:
    ams = raw_task.get("amsDetailMapping") or []
    total_weight = raw_task.get("weight")

    if not ams:
        return [{
            "print_task_id": print_task_id,
            "filament_spool_id": None,
            "slot_id": None,
            "used_weight_g": total_weight,
            "color_hex": None,
            "material": None,
        }]

    return [
        {
            "print_task_id": print_task_id,
            "filament_spool_id": None,
            "slot_id": _extract_slot_id(item),
            "used_weight_g": item.get("weight"),
            "color_hex": _convert_color(item.get("sourceColor")),
            "material": item.get("filamentType"),
        }
        for item in ams
    ]


def ingest_raw_tasks(raw_hits: list[dict], db_path: Path) -> dict[str, int]:
    stats: dict[str, int] = {"inserted": 0, "skipped": 0, "filaments": 0}

    errors: list[str] = []

    for raw in raw_hits:
        if "id" not in raw:
            errors.append(f"記錄缺少 id 欄位，已跳過：{str(raw)[:80]}")
            stats["skipped"] += 1
            continue

        try:
            with get_connection(db_path) as conn:
                device_id = raw.get("deviceId")
                printer_id = None
                if device_id:
                    printer_id = upsert_printer(
                        conn,
                        device_id=device_id,
                        name=raw.get("deviceName") or device_id,
                        model=raw.get("deviceModel"),
                    )

                task_row = {
                    "external_id": raw["id"],
                    "print_name": _extract_print_name(raw),
                    "printer_id": printer_id,
                    "started_at": raw.get("startTime"),
                    "ended_at": raw.get("endTime"),
                    "duration_seconds": raw.get("costTime"),
                    "total_weight_g": raw.get("weight"),
                    "raw_json": json.dumps(raw, ensure_ascii=False),
                }

                task_db_id = insert_print_task_ignore(conn, task_row)
                if task_db_id is None:
                    stats["skipped"] += 1
                    continue

                stats["inserted"] += 1
                for row in _build_filament_rows(raw, task_db_id):
                    insert_print_task_filament(conn, row)
                    stats["filaments"] += 1

        except Exception as exc:  # noqa: BLE001
            errors.append(f"task id={raw.get('id')} 處理失敗，已跳過：{exc}")
            stats["skipped"] += 1

    if errors:
        print(f"[WARN] 匯入時有 {len(errors)} 筆記錄發生錯誤：")
        for e in errors:
            print(f"  - {e}")

    return stats


def _parse_raw_file(raw_file: Path) -> list[dict]:
    with open(raw_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if "pages" in data:
        hits: list[dict] = []
        for page in data["pages"]:
            page_hits = page.get("hits")
            if not isinstance(page_hits, list):
                raise IngestionError(
                    f"raw_tasks.json 格式錯誤：pages[] 中的頁面缺少 hits 陣列。"
                )
            hits.extend(page_hits)
        return hits

    if "hits" in data:
        return data["hits"]

    raise IngestionError(
        "raw_tasks.json 格式無法識別。預期格式：{\"pages\": [...]} 或 {\"hits\": [...]} 或 [...]"
    )


def run_ingestion_from_file(raw_file: Path, db_path: Path) -> dict[str, int]:
    if not raw_file.exists():
        raise IngestionError(f"找不到 raw_tasks.json：{raw_file}")
    hits = _parse_raw_file(raw_file)
    if not hits:
        raise IngestionError("raw_tasks.json 中沒有任何列印記錄。")
    return ingest_raw_tasks(hits, db_path)


def run_ingestion_from_cloud(config: AppConfig, db_path: Path) -> dict[str, int]:
    from .cloud_client import BambuCloudClient
    client = BambuCloudClient(config)
    hits = client.fetch_all_tasks()
    client.save_raw_tasks(config.output_dir / "raw_tasks.json")
    return ingest_raw_tasks(hits, db_path)
