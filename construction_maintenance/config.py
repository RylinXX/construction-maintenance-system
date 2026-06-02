from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
DEFAULT_DATABASE = INSTANCE_DIR / "construction.sqlite3"
DEFAULT_UPLOAD_FOLDER = BASE_DIR / "uploads"
ARK_BASE_URL = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
ARK_MODEL = os.getenv("ARK_MODEL", "doubao-seed-2-0-pro-260215")
ARK_API_KEY = os.getenv(
    "ARK_API_KEY",
    "ark-5f20ce3d-45e4-407a-ae78-e6bc0357e401-5e232",
)
