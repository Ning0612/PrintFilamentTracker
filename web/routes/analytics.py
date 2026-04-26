from flask import Blueprint, abort, current_app, render_template, request

from src.analytics import (
    get_color_swatch_payload,
    get_cost_chart_payload,
    get_heatmap_payload,
    get_heatmap_year_payload,
    get_material_chart_payload,
    get_monthly_trend_payload,
    get_printer_chart_payload,
)
from src.db import get_connection

bp = Blueprint("analytics", __name__)


@bp.route("/")
def index():
    db_path = current_app.config["DB_PATH"]
    with get_connection(db_path) as conn:
        heatmap = get_heatmap_payload(conn)
        material = get_material_chart_payload(conn)
        cost = get_cost_chart_payload(conn)
        colors = get_color_swatch_payload(conn)
        trend = get_monthly_trend_payload(conn)
        printers = get_printer_chart_payload(conn)

    return render_template(
        "analytics/index.html",
        heatmap=heatmap,
        material=material,
        cost=cost,
        colors=colors,
        trend=trend,
        printers=printers,
    )


@bp.route("/heatmap")
def heatmap_fragment():
    year = request.args.get("year", type=int)
    if not year or year < 2000 or year > 2100:
        abort(400)
    db_path = current_app.config["DB_PATH"]
    with get_connection(db_path) as conn:
        heatmap = get_heatmap_year_payload(conn, year)
    return render_template("analytics/_heatmap.html", heatmap=heatmap)
