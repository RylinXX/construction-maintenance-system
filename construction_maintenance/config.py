from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = Path(os.getenv("CAM_INSTANCE_DIR", str(BASE_DIR / "instance")))
DEFAULT_DATABASE = INSTANCE_DIR / "construction.sqlite3"
DEFAULT_UPLOAD_FOLDER = Path(os.getenv("CAM_UPLOAD_FOLDER", str(BASE_DIR / "uploads")))
ARK_BASE_URL = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
ARK_MODEL = os.getenv("ARK_MODEL", "doubao-seed-2-0-pro-260215")
ARK_API_KEY = os.getenv("ARK_API_KEY", "")

SECRET_KEY = os.getenv("CAM_SECRET_KEY")
ADMIN_USERNAME = os.getenv("CAM_ADMIN_USERNAME")
ADMIN_PASSWORD_HASH = os.getenv("CAM_ADMIN_PASSWORD_HASH")
AUTH_REQUIRED = os.getenv("CAM_AUTH_REQUIRED", "1") == "1"
CSRF_ENABLED = os.getenv("CAM_CSRF_ENABLED", "1") == "1"
SESSION_COOKIE_SECURE = os.getenv("CAM_SESSION_COOKIE_SECURE", "1") == "1"
SEED_DEMO_DATA = os.getenv("CAM_SEED_DEMO_DATA", "0") == "1"
MAX_CONTENT_LENGTH = int(os.getenv("CAM_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
