from __future__ import annotations

import pytest

from construction_maintenance import repositories as repo


def test_create_project_and_voucher(app):
    with app.app_context():
        main_company = repo.get_main_company()
        project_id = repo.create_project(
            {
                "company_id": main_company["id"],
                "name": "土方工程",
                "status": "进行中",
                "owner": "张三",
                "start_date": "2026-05-29",
                "end_date": "",
                "notes": "",
            }
        )
        voucher_id = repo.create_voucher(
            {
                "project_id": project_id,
                "voucher_date": "2026-05-29",
                "voucher_type": "材料费用",
                "amount": 2300,
                "notes": "购买材料",
                "attachment_path": "",
                "entry_user": "财务",
            }
        )
        vouchers = repo.list_vouchers(project_id=project_id)

    assert voucher_id > 0
    assert vouchers[0]["project_name"] == "土方工程"
    assert vouchers[0]["amount"] == 2300


def test_voucher_amount_validation():
    with pytest.raises(ValueError, match="金额必须大于 0"):
        repo.normalize_amount("0")
