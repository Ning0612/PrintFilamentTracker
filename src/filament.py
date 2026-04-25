import uuid
from pathlib import Path
from typing import Any

from .db import (
    DatabaseError,
    delete_spool,
    get_all_spools,
    get_connection,
    get_ptf_by_id,
    get_spool_by_id,
    get_spool_used_weight,
    get_unmapped_filaments,
    insert_spool,
    map_filament_to_spool,
    update_spool,
)


class SpoolNotFoundError(Exception):
    pass


class SpoolValidationError(Exception):
    pass


# --- Computed fields ---

def _compute_status(initial_g: float, remaining_g: float, opened_at: Any) -> str:
    if opened_at is None:
        return "sealed"
    if remaining_g <= 0:
        return "empty"
    if initial_g > 0 and remaining_g / initial_g < 0.1:
        return "low"
    return "active"


def enrich_spool(spool_row, used_weight: float) -> dict:
    d = dict(spool_row)
    initial = d["initial_weight_g"] or 0.0
    remaining = initial - used_weight
    d["used_weight_g"] = used_weight
    d["remaining_weight_g"] = remaining
    d["usage_ratio"] = (used_weight / initial) if initial > 0 else 0.0
    d["status"] = _compute_status(initial, remaining, d.get("opened_at"))
    return d


def _validate_spool_data(data: dict) -> None:
    if not data.get("initial_weight_g"):
        raise SpoolValidationError("initial_weight_g 為必填欄位。")
    try:
        val = float(data["initial_weight_g"])
        if val <= 0:
            raise SpoolValidationError("initial_weight_g 必須大於 0。")
    except (ValueError, TypeError):
        raise SpoolValidationError("initial_weight_g 必須為數字。")


# --- CRUD ---

def create_spool(db_path: Path, data: dict) -> int:
    _validate_spool_data(data)
    if not data.get("uid"):
        data = {**data, "uid": str(uuid.uuid4())}
    with get_connection(db_path) as conn:
        return insert_spool(conn, data)


def read_spool(db_path: Path, spool_id: int) -> dict:
    with get_connection(db_path) as conn:
        row = get_spool_by_id(conn, spool_id)
        if row is None:
            raise SpoolNotFoundError(f"Spool id={spool_id} 不存在。")
        used = get_spool_used_weight(conn, spool_id)
        return enrich_spool(row, used)


def update_spool_data(db_path: Path, spool_id: int, data: dict) -> None:
    _validate_spool_data(data)
    with get_connection(db_path) as conn:
        if get_spool_by_id(conn, spool_id) is None:
            raise SpoolNotFoundError(f"Spool id={spool_id} 不存在。")
        update_spool(conn, spool_id, data)


def delete_spool_data(db_path: Path, spool_id: int) -> None:
    with get_connection(db_path) as conn:
        if get_spool_by_id(conn, spool_id) is None:
            raise SpoolNotFoundError(f"Spool id={spool_id} 不存在。")
        delete_spool(conn, spool_id)


def list_spools(db_path: Path) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = get_all_spools(conn)
        # 批次取得所有 spool 的 used_weight（單一查詢，避免 N+1）
        used_map = _get_all_used_weights(conn)
        return [enrich_spool(row, used_map.get(row["id"], 0.0)) for row in rows]


def _get_all_used_weights(conn) -> dict[int, float]:
    rows = conn.execute(
        """
        SELECT filament_spool_id, COALESCE(SUM(used_weight_g), 0.0) AS total
        FROM print_task_filament
        WHERE filament_spool_id IS NOT NULL
        GROUP BY filament_spool_id
        """
    ).fetchall()
    return {r["filament_spool_id"]: r["total"] for r in rows}


# --- Unmapped & Mapping ---

def list_unmapped(db_path: Path) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = get_unmapped_filaments(conn)
        return [dict(r) for r in rows]


def do_map(db_path: Path, ptf_id: int, spool_id: int) -> None:
    with get_connection(db_path) as conn:
        if get_spool_by_id(conn, spool_id) is None:
            raise SpoolNotFoundError(f"Spool id={spool_id} 不存在。")
        if get_ptf_by_id(conn, ptf_id) is None:
            raise SpoolNotFoundError(f"耗材記錄 id={ptf_id} 不存在。")
        try:
            map_filament_to_spool(conn, ptf_id, spool_id)
        except DatabaseError as exc:
            raise SpoolNotFoundError(str(exc)) from exc
