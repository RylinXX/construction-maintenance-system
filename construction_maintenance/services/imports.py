from __future__ import annotations

import mimetypes
from pathlib import Path
from uuid import uuid4

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


def _secure_upload_filename(file: FileStorage) -> str:
    raw_filename = file.filename or "upload"
    filename = secure_filename(raw_filename) or "upload"
    original_suffix = Path(raw_filename).suffix.lower()

    if Path(filename).suffix:
        return filename

    if original_suffix:
        base = filename
        if base.lower() == original_suffix.lstrip("."):
            base = "upload"
        return f"{base}{original_suffix}"

    guessed_suffix = mimetypes.guess_extension(file.mimetype or "")
    if guessed_suffix:
        return f"{filename}{guessed_suffix}"

    return filename


def save_upload(upload_folder: Path, file: FileStorage) -> Path:
    original = _secure_upload_filename(file)
    filename = f"{uuid4().hex}_{original}"
    upload_folder.mkdir(parents=True, exist_ok=True)
    target = upload_folder / filename
    file.save(target)
    return target
