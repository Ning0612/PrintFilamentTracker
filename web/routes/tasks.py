from flask import Blueprint, current_app, render_template, request

from src.db import get_connection, get_task_with_filaments, get_tasks_page

bp = Blueprint("tasks", __name__)

PER_PAGE = 20


@bp.route("/")
def list_view():
    db_path = current_app.config["DB_PATH"]
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()

    with get_connection(db_path) as conn:
        tasks, total = get_tasks_page(conn, page, PER_PAGE, search)

    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = max(1, min(page, total_pages))

    return render_template(
        "tasks/list.html",
        tasks=tasks,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
    )


@bp.route("/<int:task_id>")
def detail_view(task_id: int):
    db_path = current_app.config["DB_PATH"]
    with get_connection(db_path) as conn:
        task = get_task_with_filaments(conn, task_id)

    if task is None:
        return render_template("tasks/list.html", tasks=[], page=1, total_pages=1, total=0, search=""), 404

    return render_template("tasks/detail.html", task=task)
