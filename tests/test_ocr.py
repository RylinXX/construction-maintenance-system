from __future__ import annotations

from io import BytesIO

from werkzeug.datastructures import FileStorage

from construction_maintenance.services.imports import save_upload
from construction_maintenance.services.ocr import BatchOcrResult
from construction_maintenance.services.ocr import UnsupportedFileType
from construction_maintenance.services.ocr import recognize_batch_upload


class FakeRecognizer:
    def recognize_image(self, path, item_type):
        return BatchOcrResult(
            status="已识别",
            data={"amount": 1200, "voucher_type": "材料费用"},
            confidence=0.9,
        )


def test_recognize_batch_upload_accepts_images(tmp_path):
    file = FileStorage(
        stream=BytesIO(b"fake image"),
        filename="pay.jpg",
        content_type="image/jpeg",
    )
    stored = save_upload(tmp_path, file)

    result = recognize_batch_upload(stored, "voucher", recognizer=FakeRecognizer())

    assert result.status == "已识别"
    assert result.data["amount"] == 1200
    assert result.confidence == 0.9


def test_recognize_batch_upload_skips_pdf(tmp_path):
    file = FileStorage(
        stream=BytesIO(b"%PDF-1.4"),
        filename="id-card.pdf",
        content_type="application/pdf",
    )
    stored = save_upload(tmp_path, file)

    result = recognize_batch_upload(stored, "person", recognizer=FakeRecognizer())

    assert result.status == "待确认"
    assert result.data["message"] == UnsupportedFileType.message
