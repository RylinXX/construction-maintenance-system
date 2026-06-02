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


def test_create_batch_item(app):
    with app.app_context():
        item_id = repo.create_batch_item(
            {
                "item_type": "voucher",
                "source_filename": "pay.png",
                "stored_path": "uploads/pay.png",
                "status": "待确认",
                "recognized_json": "{}",
                "confidence": None,
            }
        )
        items = repo.list_batch_items("voucher")

    assert item_id > 0
    assert items[0]["source_filename"] == "pay.png"


def test_update_batch_item_recognition(app):
    with app.app_context():
        item_id = repo.create_batch_item(
            {
                "item_type": "voucher",
                "source_filename": "pay.png",
                "stored_path": "pay.png",
            }
        )
        repo.update_batch_item_recognition(
            item_id,
            status="已识别",
            recognized_json='{"amount": 1200}',
            confidence=0.86,
        )
        item = repo.list_batch_items("voucher")[0]

    assert item["status"] == "已识别"
    assert item["recognized_json"] == '{"amount": 1200}'
    assert item["confidence"] == 0.86


def test_expense_category_rename_updates_existing_vouchers(app):
    with app.app_context():
        category_id = repo.create_expense_category({"name": "机械租赁", "sort_order": 25})
        main_company = repo.get_main_company()
        project_id = repo.create_project(
            {
                "company_id": main_company["id"],
                "name": "道路维修",
            }
        )
        repo.create_voucher(
            {
                "project_id": project_id,
                "voucher_date": "2026-05-29",
                "voucher_type": "机械租赁",
                "amount": 1200,
            }
        )

        repo.update_expense_category(
            category_id,
            {"name": "设备租赁", "sort_order": 30, "is_active": 0},
        )
        active_names = repo.list_expense_category_names()
        all_categories = repo.list_expense_categories(include_inactive=True)
        voucher = repo.list_vouchers(project_id=project_id)[0]

    assert "机械租赁" not in active_names
    assert "设备租赁" not in active_names
    assert next(row for row in all_categories if row["id"] == category_id)["name"] == "设备租赁"
    assert voucher["voucher_type"] == "设备租赁"


def test_person_id_card_path_can_be_saved_and_replaced(app):
    with app.app_context():
        person_id = repo.create_person(
            {
                "name": "李工",
                "id_number": "410000199001019999",
                "id_card_path": "old-id-card.jpg",
            }
        )
        repo.update_person(
            person_id,
            {
                "name": "李工",
                "id_number": "410000199001019999",
                "id_card_path": "new-id-card.jpg",
            },
        )
        person = repo.list_people()[0]

    assert person["id_card_path"] == "new-id-card.jpg"


def test_attendance_operations(app):
    with app.app_context():
        # 1. 创建测试人员
        person_id = repo.create_person(
            {
                "name": "王大锤",
                "id_number": "410000199001018888",
            }
        )
        
        # 2. 保存白班考勤
        repo.save_attendance(person_id, "2026-06-02", "白班")
        records = repo.list_attendance_by_month("2026-06")
        assert len(records) == 1
        assert records[0]["person_id"] == person_id
        assert records[0]["work_date"] == "2026-06-02"
        assert records[0]["shift_type"] == "白班"

        # 3. 幂等更新为夜班考勤
        repo.save_attendance(person_id, "2026-06-02", "夜班")
        records = repo.list_attendance_by_month("2026-06")
        assert len(records) == 1
        assert records[0]["shift_type"] == "夜班"

        # 4. 删除考勤记录
        repo.save_attendance(person_id, "2026-06-02", None)
        records = repo.list_attendance_by_month("2026-06")
        assert len(records) == 0

