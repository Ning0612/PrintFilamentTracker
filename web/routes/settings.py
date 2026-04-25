import threading
from pathlib import Path

import requests
from flask import Blueprint, current_app, flash, make_response, render_template, request, session, url_for

bp = Blueprint("settings", __name__, url_prefix="/settings")

_GLOBAL_BASE = "https://api.bambulab.com"
_CHINA_BASE = "https://api.bambulab.cn"
_LOGIN_PATH = "/v1/user-service/user/login"
_SEND_CODE_PATH = "/v1/user-service/user/sendemail/code"
_TFA_PATH = "/api/sign-in/tfa"
_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "bambu_network_agent/01.09.05.01",
}
_TIMEOUT = 20

_sync_lock = threading.Lock()
_sync_state: dict = {"status": "idle", "message": "", "stats": None}


def _api_post(base_url: str, path: str, payload: dict) -> tuple[dict | None, str | None]:
    try:
        resp = requests.post(base_url + path, json=payload, headers=_HEADERS, timeout=_TIMEOUT)
    except requests.Timeout:
        return None, f"連線逾時（{_TIMEOUT} 秒），請確認網路連線。"
    except requests.RequestException as exc:
        return None, f"網路錯誤：{exc}"
    if not resp.ok:
        return None, f"伺服器回傳 HTTP {resp.status_code}：{resp.text[:200]}"
    try:
        return resp.json(), None
    except ValueError:
        return None, "伺服器回傳非 JSON 格式"


def _write_env(token: str, region: str, env_path: Path) -> None:
    lines = []
    has_token = has_region = False
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.lstrip()
            if stripped.startswith("BAMBU_ACCESS_TOKEN="):
                lines.append(f"BAMBU_ACCESS_TOKEN={token}")
                has_token = True
            elif stripped.startswith("BAMBU_REGION="):
                lines.append(f"BAMBU_REGION={region}")
                has_region = True
            else:
                lines.append(line)
    if not has_token:
        lines.append(f"BAMBU_ACCESS_TOKEN={token}")
    if not has_region:
        lines.append(f"BAMBU_REGION={region}")

    # Atomic write: write to temp then rename
    tmp_path = env_path.with_suffix(".env.tmp")
    tmp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp_path.replace(env_path)


def _apply_token(token: str, region: str) -> None:
    env_path = current_app.config.get("ENV_PATH")
    if env_path:
        try:
            _write_env(token, region, Path(env_path))
        except OSError as exc:
            current_app.logger.warning("無法寫入 .env：%s", exc)
    # Only update token/region; preserve any custom BAMBU_API_BASE
    current_app.config["BAMBU_TOKEN"] = token
    current_app.config["BAMBU_REGION"] = region


def _mask_token(token: str) -> str:
    if not token:
        return "(未設定)"
    if len(token) <= 8:
        return "***"
    return token[:4] + "..." + token[-4:]


@bp.route("/")
def index():
    token = current_app.config.get("BAMBU_TOKEN", "")
    region = current_app.config.get("BAMBU_REGION", "global")
    return render_template(
        "settings/index.html",
        token_masked=_mask_token(token),
        has_token=bool(token),
        region=region,
        sync_state=_sync_state,
    )


@bp.route("/login/form")
def login_form():
    return render_template("settings/_login_form.html")


@bp.route("/login/step1", methods=["POST"])
def login_step1():
    email = request.form.get("email", "").strip()
    # Do NOT strip password — leading/trailing spaces may be intentional
    password = request.form.get("password", "")
    region = request.form.get("region", "global")
    if region not in ("global", "china"):
        region = "global"

    if not email or not password:
        return render_template("settings/_login_error.html", error="Email 和密碼不得為空。")

    base_url = _GLOBAL_BASE if region == "global" else _CHINA_BASE
    data, err = _api_post(base_url, _LOGIN_PATH, {
        "account": email, "password": password, "apiError": "",
    })
    if err:
        return render_template("settings/_login_error.html", error=err)

    login_type = data.get("loginType", "")
    token = data.get("accessToken")

    if token and not login_type:
        _apply_token(token, region)
        flash("Bambu Cloud 登入成功，Token 已儲存至 .env。", "success")
        resp = make_response("")
        resp.headers["HX-Redirect"] = url_for("settings.index")
        return resp

    if login_type == "verifyCode":
        _, send_err = _api_post(base_url, _SEND_CODE_PATH, {
            "email": email, "type": "codeLogin",
        })
        if send_err:
            return render_template("settings/_login_error.html",
                                   error=f"驗證碼發送失敗：{send_err}")
        session["bambu_login"] = {
            "email": email, "region": region,
            "base_url": base_url, "type": "verifyCode",
        }
        return render_template("settings/_login_step2.html",
                               login_type="verifyCode", email=email)

    if login_type == "tfa":
        session["bambu_login"] = {
            "email": email, "region": region,
            "base_url": base_url, "type": "tfa",
            "tfa_key": data.get("tfaKey", ""),
        }
        return render_template("settings/_login_step2.html",
                               login_type="tfa", email=email)

    return render_template("settings/_login_error.html",
                           error=f"未預期的登入回應：{data}")


@bp.route("/login/step2", methods=["POST"])
def login_step2():
    info = session.get("bambu_login")
    if not info:
        return render_template("settings/_login_error.html",
                               error="登入工作階段已過期，請重新開始。")

    code = request.form.get("code", "").strip()
    if not code:
        return render_template("settings/_login_error.html", error="驗證碼不得為空。")

    base_url = info["base_url"]
    region = info["region"]

    if info["type"] == "verifyCode":
        data, err = _api_post(base_url, _LOGIN_PATH, {
            "account": info["email"], "code": code,
        })
    else:
        data, err = _api_post(base_url, _TFA_PATH, {
            "tfaKey": info.get("tfa_key", ""), "tfaCode": code,
        })

    if err:
        return render_template("settings/_login_error.html", error=err)

    token = data.get("accessToken") if data else None
    if not token:
        return render_template("settings/_login_error.html",
                               error=f"登入失敗，伺服器回應：{data}")

    session.pop("bambu_login", None)
    _apply_token(token, region)
    flash("Bambu Cloud 登入成功，Token 已儲存至 .env。", "success")
    resp = make_response("")
    resp.headers["HX-Redirect"] = url_for("settings.index")
    return resp


@bp.route("/sync", methods=["POST"])
def start_sync():
    global _sync_state

    # Atomic check-and-set to prevent concurrent syncs
    with _sync_lock:
        if _sync_state.get("status") == "running":
            return render_template("settings/_sync_status.html", sync_state=_sync_state)

        token = current_app.config.get("BAMBU_TOKEN", "")
        if not token:
            _sync_state = {"status": "error",
                           "message": "尚未設定 Token，請先登入 Bambu 帳號。",
                           "stats": None}
            return render_template("settings/_sync_status.html", sync_state=_sync_state)

        _sync_state = {"status": "running",
                       "message": "正在從 Bambu Cloud 下載列印歷史...",
                       "stats": None}

    db_path = current_app.config["DB_PATH"]
    region = current_app.config.get("BAMBU_REGION", "global")
    # Preserve custom API base; fall back to regional default
    api_base = (
        current_app.config.get("BAMBU_API_BASE")
        or (_GLOBAL_BASE if region == "global" else _CHINA_BASE)
    )
    output_dir = db_path.parent

    from src.config import AppConfig
    config = AppConfig(
        access_token=token,
        region=region,
        api_base=api_base,
        output_dir=output_dir,
        request_timeout=30,
    )

    def _run() -> None:
        global _sync_state
        try:
            from src.ingestion import run_ingestion_from_cloud
            stats = run_ingestion_from_cloud(config, db_path)
            with _sync_lock:
                _sync_state = {
                    "status": "done",
                    "message": (
                        f"同步完成！新增 {stats['inserted']} 筆，"
                        f"略過 {stats['skipped']} 筆，"
                        f"耗材記錄 {stats['filaments']} 筆。"
                    ),
                    "stats": stats,
                }
        except Exception as exc:
            with _sync_lock:
                _sync_state = {"status": "error", "message": str(exc), "stats": None}

    threading.Thread(target=_run, daemon=True).start()
    return render_template("settings/_sync_status.html", sync_state=_sync_state)


@bp.route("/sync/status")
def sync_status():
    return render_template("settings/_sync_status.html", sync_state=_sync_state)
