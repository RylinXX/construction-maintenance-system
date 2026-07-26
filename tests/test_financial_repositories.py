import pytest

from construction_maintenance import repositories as repo
from construction_maintenance.db import get_db


def _leaf_id(name: str) -> int:
    return int(get_db().execute(
        "select id from expense_categories where name = ? and parent_id is not null",
        (name,),
    ).fetchone()["id"])


def test_structured_entries_produce_correct_project_summary(app):
    with app.app_context():
        company = repo.get_main_company()
        project_id = repo.create_project({"company_id": company["id"], "name": "测试项目"})
        rows = [
            ("支出", "材料运输费", 1000),
            ("冲减支出", "材料运输费", 100),
            ("收入", "废料处置收入", 50),
            ("资金往来", "备用金", 200),
        ]
        for index, (transaction_type, category, amount) in enumerate(rows, start=1):
            repo.create_voucher({
                "project_id": project_id,
                "voucher_date": "2026-07-01",
                "transaction_type": transaction_type,
                "category_id": _leaf_id(category),
                "amount": amount,
                "source_record_id": f"TEST-{index}",
                "payment_status": "未支付",
            })
        summary = repo.get_project_financial_summary(project_id)

    assert summary == {
        "expense": 1000.0,
        "expense_reduction": 100.0,
        "net_expense": 900.0,
        "income": 50.0,
        "fund_transfer": 200.0,
        "unsettled": 900.0,
        "entry_count": 4,
        "review_count": 0,
        "pending_count": 0,
    }


def test_used_leaf_category_cannot_be_deleted(app):
    with app.app_context():
        company = repo.get_main_company()
        project_id = repo.create_project({"company_id": company["id"], "name": "分类保护"})
        category_id = _leaf_id("机械燃油")
        repo.create_voucher({
            "project_id": project_id,
            "voucher_date": "2026-07-01",
            "transaction_type": "支出",
            "category_id": category_id,
            "amount": 300,
        })
        with pytest.raises(ValueError, match="已被财务明细使用"):
            repo.delete_expense_category(category_id)


def test_pending_item_converts_once_to_structured_entry(app):
    with app.app_context():
        company = repo.get_main_company()
        project_id = repo.create_project({"company_id": company["id"], "name": "待补录项目"})
        category_id = _leaf_id("运输车辆台班")
        item_id = repo.create_ledger_pending_item({
            "project_id": project_id,
            "item_date": "2026-03-17",
            "summary": "大车两个台班",
            "suggested_category_id": category_id,
            "source_filename": "source.xls",
            "source_sheet": "汇总",
            "source_row": 7,
            "issue_type": "缺少金额",
        })
        voucher_id = repo.convert_ledger_pending_item(
            item_id,
            amount=1200,
            category_id=category_id,
            transaction_type="支出",
            payment_status="支付状态待确认",
            actor_admin_id=None,
        )
        item = repo.get_ledger_pending_item(item_id)
        with pytest.raises(ValueError, match="已经转换"):
            repo.convert_ledger_pending_item(
                item_id,
                amount=1200,
                category_id=category_id,
                transaction_type="支出",
                payment_status="支付状态待确认",
                actor_admin_id=None,
            )

    assert item["status"] == "已转正式明细"
    assert item["voucher_id"] == voucher_id
