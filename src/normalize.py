from typing import Any


def normalize_tasks(raw_hits: list[dict]) -> list[dict[str, Any]]:
    return [normalize_task(hit) for hit in raw_hits]


def normalize_task(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "print_name":          _extract_print_name(raw),
        "printer_name":        raw.get("deviceName"),
        "printer_id":          raw.get("deviceId"),
        "started_at":          raw.get("startTime"),
        "ended_at":            raw.get("endTime"),
        "duration_seconds":    _safe_int(raw.get("costTime")),
        "filaments":           _extract_filaments(raw.get("amsDetailMapping") or []),
        "total_used_weight_g": _safe_float(raw.get("weight")),
        "raw":                 raw,
    }


def _extract_print_name(raw: dict) -> str | None:
    for key in ("title", "design_title", "name"):
        val = raw.get(key)
        if val:
            return str(val)
    return None


def _extract_filaments(ams_mapping: list[dict]) -> list[dict]:
    result = []
    for item in ams_mapping:
        result.append({
            "slot":          _safe_int(item.get("position")),
            "material":      item.get("filamentType"),
            "color":         None,
            "color_hex":     _convert_color_hex(item.get("sourceColor")),
            "used_weight_g": _safe_float(item.get("weight")),
        })
    return result


def _convert_color_hex(raw_color: str | None) -> str | None:
    if not raw_color or len(raw_color) != 8:
        return None
    try:
        int(raw_color, 16)
        return f"#{raw_color[:6].upper()}"
    except ValueError:
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
