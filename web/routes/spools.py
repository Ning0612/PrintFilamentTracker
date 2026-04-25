from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from src.filament import (
    SpoolNotFoundError,
    SpoolValidationError,
    create_spool,
    delete_spool_data,
    list_spools,
    read_spool,
    update_spool_data,
)

bp = Blueprint("spools", __name__)


@bp.route("/")
def list_view():
    db_path = current_app.config["DB_PATH"]
    spools = list_spools(db_path)
    return render_template("spools/list.html", spools=spools)


@bp.route("/new", methods=["GET", "POST"])
def new_view():
    db_path = current_app.config["DB_PATH"]
    if request.method == "POST":
        data = _form_to_spool(request.form)
        try:
            create_spool(db_path, data)
            flash("耗材已新增。", "success")
            return redirect(url_for("spools.list_view"))
        except SpoolValidationError as exc:
            flash(str(exc), "error")
    return render_template("spools/form.html", spool=None, action=url_for("spools.new_view"))


@bp.route("/<int:spool_id>/edit", methods=["GET", "POST"])
def edit_view(spool_id: int):
    db_path = current_app.config["DB_PATH"]
    try:
        spool = read_spool(db_path, spool_id)
    except SpoolNotFoundError:
        flash("找不到此耗材。", "error")
        return redirect(url_for("spools.list_view"))

    if request.method == "POST":
        data = _form_to_spool(request.form)
        try:
            update_spool_data(db_path, spool_id, data)
            flash("耗材已更新。", "success")
            return redirect(url_for("spools.list_view"))
        except SpoolValidationError as exc:
            flash(str(exc), "error")

    return render_template(
        "spools/form.html",
        spool=spool,
        action=url_for("spools.edit_view", spool_id=spool_id),
    )


@bp.route("/<int:spool_id>/delete", methods=["POST"])
def delete_view(spool_id: int):
    db_path = current_app.config["DB_PATH"]
    try:
        delete_spool_data(db_path, spool_id)
        flash("耗材已刪除。", "success")
    except SpoolNotFoundError:
        flash("找不到此耗材。", "error")
    return redirect(url_for("spools.list_view"))


def _form_to_spool(form) -> dict:
    return {
        "material": form.get("material", "").strip() or None,
        "color_name": form.get("color_name", "").strip() or None,
        "color_hex": form.get("color_hex", "").strip() or None,
        "initial_weight_g": form.get("initial_weight_g", "").strip() or None,
        "price": form.get("price", "").strip() or None,
        "purchased_at": form.get("purchased_at", "").strip() or None,
        "opened_at": form.get("opened_at", "").strip() or None,
        "product_url": form.get("product_url", "").strip() or None,
        "note": form.get("note", "").strip() or None,
    }
