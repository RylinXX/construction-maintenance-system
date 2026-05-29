from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask

from . import db
from .config import DEFAULT_DATABASE, DEFAULT_UPLOAD_FOLDER
from .web.routes import bp as web_bp


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DATABASE=DEFAULT_DATABASE,
        UPLOAD_FOLDER=DEFAULT_UPLOAD_FOLDER,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.init_db()

    app.register_blueprint(web_bp)
    return app
