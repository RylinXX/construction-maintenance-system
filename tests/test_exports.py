from __future__ import annotations

from openpyxl import load_workbook

from construction_maintenance import repositories as repo
from construction_maintenance.services.exports import build_people_workbook


def test_build_people_workbook(app, tmp_path):
    with app.app_context():
        repo.create_person(
            {
                "name": "王小明",
                "id_number": "410000199001011234",
                "gender": "男",
                "birth_date": "1990-01-01",
                "age": 36,
                "phone": "13800000000",
                "address": "河南省郑州市",
                "job_type": "普工",
                "bank_card": "6222000000000000",
                "bank_name": "建设银行",
                "entry_date": "2026-05-29",
                "notes": "",
            }
        )
        output = tmp_path / "people.xlsx"
        build_people_workbook(output)

    workbook = load_workbook(output)
    sheet = workbook.active
    assert sheet["A1"].value == "姓名"
    assert sheet["A2"].value == "王小明"
    assert sheet["B2"].value == "410000199001011234"


def test_build_qualification_workbook(app, tmp_path):
    with app.app_context():
        company = repo.get_main_company()
        repo.create_qualification(
            {
                "company_id": company["id"],
                "name": "建筑业企业资质",
                "certificate_no": "D300000",
                "issue_date": "2026-01-01",
                "expiry_date": "2029-01-01",
                "is_long_term": 0,
                "attachment_path": "",
                "notes": "",
            }
        )
        output = tmp_path / "qualifications.xlsx"
        from construction_maintenance.services.exports import build_qualification_workbook
        build_qualification_workbook(output)

    workbook = load_workbook(output)
    sheet = workbook.active
    assert sheet["A1"].value == "公司"
    assert sheet["B2"].value == "建筑业企业资质"
