from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask

from . import db
from .config import DEFAULT_DATABASE, DEFAULT_UPLOAD_FOLDER
from .config import ARK_API_KEY, ARK_BASE_URL, ARK_MODEL
from .config import ADMIN_PASSWORD_HASH, ADMIN_USERNAME, AUTH_REQUIRED, CSRF_ENABLED
from .config import SECRET_KEY
from . import security
from .web.routes import bp as web_bp


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=SECRET_KEY or "dev",
        DATABASE=DEFAULT_DATABASE,
        UPLOAD_FOLDER=DEFAULT_UPLOAD_FOLDER,
        ARK_BASE_URL=ARK_BASE_URL,
        ARK_MODEL=ARK_MODEL,
        ARK_API_KEY=ARK_API_KEY,
        ADMIN_USERNAME=ADMIN_USERNAME or "",
        ADMIN_PASSWORD_HASH=ADMIN_PASSWORD_HASH or "",
        AUTH_REQUIRED=AUTH_REQUIRED,
        CSRF_ENABLED=CSRF_ENABLED,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    if app.config["AUTH_REQUIRED"]:
        if not app.config.get("SECRET_KEY") or app.config["SECRET_KEY"] == "dev":
            raise RuntimeError("CAM_SECRET_KEY must be configured when authentication is enabled")
        if not app.config.get("ADMIN_USERNAME") or not app.config.get("ADMIN_PASSWORD_HASH"):
            raise RuntimeError(
                "CAM_ADMIN_USERNAME and CAM_ADMIN_PASSWORD_HASH must be configured "
                "when authentication is enabled"
            )

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.init_db()

    app.register_blueprint(web_bp)
    security.init_app(app)
    return app
