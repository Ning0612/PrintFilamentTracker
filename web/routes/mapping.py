from flask import Blueprint, current_app, render_template, request

from src.filament import SpoolNotFoundError, do_map, list_spools, list_unmapped

bp = Blueprint("mapping", __name__)


@bp.route("/")
def list_view():
    db_path = current_app.config["DB_PATH"]
    unmapped = list_unmapped(db_path)
    spools = list_spools(db_path)
    return render_template("mapping/unmapped.html", unmapped=unmapped, spools=spools)


@bp.route("/<int:ptf_id>/map", methods=["POST"])
def map_view(ptf_id: int):
    db_path = current_app.config["DB_PATH"]
    spool_id_str = request.form.get("spool_id", "").strip()

    if not spool_id_str:
        return _row_error(ptf_id, "請選擇一個 spool。")

    try:
        spool_id = int(spool_id_str)
        do_map(db_path, ptf_id, spool_id)
    except (ValueError, SpoolNotFoundError) as exc:
        return _row_error(ptf_id, str(exc))

    spools = list_spools(db_path)
    spool = next((s for s in spools if s["id"] == spool_id), None)
    return render_template("mapping/mapped_row.html", ptf_id=ptf_id, spool=spool)


def _row_error(ptf_id: int, msg: str) -> str:
    return render_template("mapping/error_row.html", ptf_id=ptf_id, msg=msg)
