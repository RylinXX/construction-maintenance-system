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
    assert [cell.value for cell in sheet[1]] == [
        "姓名",
        "身份证号",
        "性别",
        "出生日期",
        "年龄",
        "电话",
        "住址",
        "岗位/工种",
        "银行卡号",
        "开户行",
        "入职/进场日期",
        "备注",
    ]
    assert [cell.value for cell in sheet[2]] == [
        "王小明",
        "410000199001011234",
        "男",
        "1990-01-01",
        36,
        "13800000000",
        "河南省郑州市",
        "普工",
        "6222000000000000",
        "建设银行",
        "2026-05-29",
        None,
    ]
