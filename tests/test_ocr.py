from __future__ import annotations

import base64
import json
from io import BytesIO
import struct

import fitz
from werkzeug.datastructures import FileStorage

from construction_maintenance.services.ocr import ArkOcrRecognizer
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


def test_recognize_batch_upload_accepts_pdf(tmp_path):
    file = FileStorage(
        stream=BytesIO(b"fake pdf data"),
        filename="id-card.pdf",
        content_type="application/pdf",
    )
    stored = save_upload(tmp_path, file)

    result = recognize_batch_upload(stored, "person", recognizer=FakeRecognizer())

    assert result.status == "已识别"
    assert result.data["amount"] == 1200
    assert result.confidence == 0.9


def test_ocr_does_not_upscale_small_images(tmp_path, monkeypatch):
    image_path = tmp_path / "small.png"
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 2, 1), False)
    pixmap.clear_with(255)
    pixmap.save(image_path)
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            body = {"choices": [{"message": {"content": '{"confidence": 0.9}'}}]}
            return json.dumps(body).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    recognizer = ArkOcrRecognizer(
        base_url="https://example.test/api/v3",
        model="test-model",
        api_key="test-key",
    )

    result = recognizer.recognize_image(image_path, "voucher")

    assert result.status == "已识别"
    assert captured["timeout"] == 45
    payload = json.loads(captured["request"].data)
    image_url = payload["messages"][0]["content"][1]["image_url"]["url"]
    encoded_image = image_url.split(",", 1)[1]
    png = base64.b64decode(encoded_image)
    width, height = struct.unpack(">II", png[16:24])
    assert (width, height) == (2, 1)
