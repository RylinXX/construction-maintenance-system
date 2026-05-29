from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
DEFAULT_DATABASE = INSTANCE_DIR / "construction.sqlite3"
DEFAULT_UPLOAD_FOLDER = BASE_DIR / "uploads"
