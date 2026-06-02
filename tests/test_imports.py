from __future__ import annotations

from io import BytesIO

from werkzeug.datastructures import FileStorage

from construction_maintenance.services.imports import save_upload


def test_save_upload_preserves_extension_for_chinese_pdf_name(tmp_path):
    file = FileStorage(
        stream=BytesIO(b"%PDF-1.4"),
        filename="身份证.pdf",
        content_type="application/pdf",
    )

    stored = save_upload(tmp_path, file)

    assert stored.suffix == ".pdf"
    assert stored.exists()
