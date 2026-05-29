from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


def save_upload(upload_folder: Path, file: FileStorage) -> Path:
    original = secure_filename(file.filename or "upload")
    filename = f"{uuid4().hex}_{original}"
    upload_folder.mkdir(parents=True, exist_ok=True)
    target = upload_folder / filename
    file.save(target)
    return target
