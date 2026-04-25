from flask import Blueprint, current_app, render_template

from src.db import get_connection, get_recent_tasks
from src.filament import list_spools, list_unmapped

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    db_path = current_app.config["DB_PATH"]
    spools = list_spools(db_path)
    unmapped_count = len(list_unmapped(db_path))

    stats = {
        "total": len(spools),
        "active": sum(1 for s in spools if s["status"] == "active"),
        "low": sum(1 for s in spools if s["status"] == "low"),
        "sealed": sum(1 for s in spools if s["status"] == "sealed"),
        "empty": sum(1 for s in spools if s["status"] == "empty"),
    }

    with get_connection(db_path) as conn:
        recent_tasks = get_recent_tasks(conn, limit=10)

    return render_template(
        "dashboard.html",
        spools=spools,
        stats=stats,
        unmapped_count=unmapped_count,
        recent_tasks=recent_tasks,
    )
