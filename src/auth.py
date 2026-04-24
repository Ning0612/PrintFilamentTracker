class AuthError(Exception):
    pass


def build_auth_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def mask_token(access_token: str) -> str:
    if not access_token or len(access_token) < 8:
        return "[INVALID_TOKEN]"
    return access_token[:8] + "..."


def handle_auth_error(status_code: int, masked_token: str) -> None:
    raise AuthError(
        f"[ERROR] 認證失敗（HTTP {status_code}）。\n"
        f"Token（{masked_token}）可能已過期或無效。\n"
        "請重新取得 access token 並更新 .env 中的 BAMBU_ACCESS_TOKEN。"
    )
