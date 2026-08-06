from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any

from flask import Flask, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from . import db
from .config import DEFAULT_DATABASE, DEFAULT_UPLOAD_FOLDER
from .config import ARK_API_KEY, ARK_BASE_URL, ARK_MODEL
from .config import ADMIN_PASSWORD_HASH, ADMIN_USERNAME, AUTH_REQUIRED, CSRF_ENABLED
from .config import SESSION_COOKIE_SECURE
from .config import MAX_CONTENT_LENGTH, SEED_DEMO_DATA
from .config import SECRET_KEY
from . import security
from . import commands
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
        SESSION_COOKIE_SECURE=SESSION_COOKIE_SECURE,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
        SEED_DEMO_DATA=SEED_DEMO_DATA,
        TEMPLATES_AUTO_RELOAD=True,
        APP_VERSION="0.3.0",
    )
    if test_config:
        app.config.update(test_config)

    if app.config["AUTH_REQUIRED"]:
        if not app.config.get("SECRET_KEY") or app.config["SECRET_KEY"] == "dev":
            raise RuntimeError("CAM_SECRET_KEY must be configured when authentication is enabled")
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.init_db()
        if app.config["AUTH_REQUIRED"]:
            admin_count = db.get_db().execute(
                "select count(*) from admin_users"
            ).fetchone()[0]
            if admin_count == 0:
                raise RuntimeError(
                    "No administrator account exists. Configure "
                    "CAM_ADMIN_USERNAME and CAM_ADMIN_PASSWORD_HASH for bootstrap."
                )

    app.register_blueprint(web_bp)
    commands.init_app(app)
    security.init_app(app)

    @app.route("/health")
    def health_check():
        return jsonify(status="healthy", version=app.config.get("APP_VERSION", "0.3.0")), 200

    @app.errorhandler(ValueError)
    def handle_invalid_input(error: ValueError):
        if request.is_json:
            return jsonify(status="error", message=str(error)), 400
        return str(error), 400

    @app.errorhandler(RequestEntityTooLarge)
    def handle_upload_too_large(_error: RequestEntityTooLarge):
        message = "上传文件过大，单次请求不能超过 20MB"
        if request.is_json:
            return jsonify(status="error", message=message), 413
        return message, 413

    @app.errorhandler(sqlite3.IntegrityError)
    def handle_data_conflict(_error: sqlite3.IntegrityError):
        message = "提交的数据无效、重复，或关联记录不存在"
        if request.is_json:
            return jsonify(status="error", message=message), 400
        return message, 400

    return app
