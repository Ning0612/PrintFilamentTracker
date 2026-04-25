from pathlib import Path

from flask import Flask

from src.config import load_config
from src.db import get_db_path, init_db


def create_app(db_path: Path | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    if db_path is None:
        config = load_config()
        config.output_dir.mkdir(parents=True, exist_ok=True)
        db_path = get_db_path(config.output_dir)

    init_db(db_path)
    app.config["DB_PATH"] = db_path
    app.secret_key = "bambu-print-manager-local"

    from web.routes.dashboard import bp as dashboard_bp
    from web.routes.mapping import bp as mapping_bp
    from web.routes.spools import bp as spools_bp
    from web.routes.tasks import bp as tasks_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(spools_bp, url_prefix="/spools")
    app.register_blueprint(tasks_bp, url_prefix="/tasks")
    app.register_blueprint(mapping_bp, url_prefix="/mapping")

    return app
