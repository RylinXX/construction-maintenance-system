from __future__ import annotations

from io import BytesIO

from openpyxl import load_workbook

from construction_maintenance import create_app
from construction_maintenance import repositories as repo
from construction_maintenance.db import get_db
from construction_maintenance.services.exports import build_people_workbook


def test_production_initialization_does_not_seed_demo_business_data(tmp_path):
    app = create_app(
        {
            "TESTING": False,
            "DATABASE": tmp_path / "production.sqlite3",
            "UPLOAD_FOLDER": tmp_path / "uploads",
            "AUTH_REQUIRED": False,
            "CSRF_ENABLED": False,
            "SEED_DEMO_DATA": False,
        }
    )
    with app.app_context():
        assert get_db().execute("select count(*) from people").fetchone()[0] == 0
        assert get_db().execute("select count(*) from projects").fetchone()[0] == 0
        assert get_db().execute("select count(*) from vouchers").fetchone()[0] == 0


def test_missing_attachment_returns_real_404(client):
    response = client.get("/uploads/definitely-missing.pdf")
    assert response.status_code == 404
    assert response.mimetype != "image/svg+xml"


def test_security_headers_are_present(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "camera=()" in response.headers["Permissions-Policy"]


def test_invalid_month_and_attendance_payloads_do_not_raise_500(client):
    assert client.get("/people?tab=attendance&month=2026-13").status_code == 200
    response = client.post(
        "/attendance/update",
        json={"person_id": "bad", "date": "not-a-date", "shift_type": "未知"},
    )
    assert response.status_code == 400
    response = client.post(
        "/attendance/batch-fill",
        json={"month": "2026-13", "shift_type": "上班"},
    )
    assert response.status_code == 400


def test_disallowed_upload_is_rejected_without_writing_file(client, app):
    response = client.post(
        "/batch",
        data={
            "item_type": "voucher",
            "files": (BytesIO(b"<script>alert(1)</script>"), "invoice.html"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert not list(app.config["UPLOAD_FOLDER"].iterdir())


def test_voucher_void_keeps_history_and_excludes_financial_totals(client, app):
    with app.app_context():
        project_id = repo.create_project(
            {"company_id": 1, "name": "作废测试项目", "status": "进行中"}
        )
        voucher_id = repo.create_voucher(
            {
                "project_id": project_id,
                "voucher_date": "2026-07-20",
                "voucher_type": "材料费用",
                "amount": 99.5,
            }
        )

    response = client.post(
        f"/vouchers/{voucher_id}/void",
        data={"reason": "重复录入"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "已作废".encode() in response.data

    with app.app_context():
        assert repo.list_vouchers() == []
        historical = repo.list_vouchers(include_voided=True)
        assert len(historical) == 1
        assert historical[0]["void_reason"] == "重复录入"
        audit = repo.list_audit_events()
        assert any(row["action"] == "void" for row in audit)


def test_deleting_uploaded_person_removes_physical_file(client, app):
    stored = app.config["UPLOAD_FOLDER"] / "person-id.pdf"
    stored.write_bytes(b"%PDF-1.4")
    with app.app_context():
        person_id = repo.create_person(
            {
                "name": "附件清理测试",
                "id_number": "410000199001011234",
                "id_card_path": stored.name,
            }
        )

    response = client.post(f"/people/{person_id}/delete")
    assert response.status_code == 302
    assert not stored.exists()


def test_excel_export_escapes_formula_like_user_text(app, tmp_path):
    with app.app_context():
        repo.create_person(
            {"name": "=2+2", "id_number": "410000199001011234"}
        )
        output = build_people_workbook(tmp_path / "people.xlsx")

    sheet = load_workbook(output).active
    assert sheet["A2"].value == "'=2+2"


def test_qualification_recognition_never_returns_mock_data(client):
    response = client.post(
        "/qualifications/recognize",
        data={"attachment": (BytesIO(b"\xff\xd8\xff\xe0test"), "营业执照.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 503
    assert response.json["success"] is False
    assert "91410100" not in response.get_data(as_text=True)
