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


def test_root_scope_change_is_rejected_when_children_exist(app):
    with app.app_context():
        root = get_db().execute(
            "select * from expense_categories where name = '材料费'"
        ).fetchone()

        with pytest.raises(ValueError, match="一级分类仍有二级分类，不能修改收支范围"):
            repo.update_expense_category(
                int(root["id"]),
                {
                    "name": root["name"],
                    "parent_id": None,
                    "transaction_scope": "收入",
                    "sort_order": root["sort_order"],
                    "is_active": 1,
                },
            )

        scopes = {
            row["transaction_scope"]
            for row in get_db().execute(
                "select transaction_scope from expense_categories where id = ? or parent_id = ?",
                (root["id"], root["id"]),
            )
        }

    assert scopes == {"支出"}


@pytest.mark.parametrize(
    ("parent_name", "deactivate_parent", "transaction_scope", "message"),
    [
        ("五金辅材及工具", False, "支出", "所属分类必须是启用的一级分类"),
        ("材料费", True, "支出", "所属分类必须是启用的一级分类"),
        ("材料费", False, "收入", "分类与收支范围不匹配"),
    ],
)
def test_create_leaf_requires_active_root_with_matching_scope(
    app, parent_name, deactivate_parent, transaction_scope, message
):
    with app.app_context():
        parent = get_db().execute(
            "select * from expense_categories where name = ?", (parent_name,)
        ).fetchone()
        if deactivate_parent:
            get_db().execute(
                "update expense_categories set is_active = 0 where id = ?",
                (parent["id"],),
            )
            get_db().commit()

        with pytest.raises(ValueError, match=message):
            repo.create_expense_category(
                {
                    "name": f"伪造分类-{parent_name}",
                    "parent_id": int(parent["id"]),
                    "transaction_scope": transaction_scope,
                    "sort_order": 999,
                }
            )

        created = get_db().execute(
            "select count(*) from expense_categories where name = ?",
            (f"伪造分类-{parent_name}",),
        ).fetchone()[0]

    assert created == 0


def test_voucher_listing_supports_stable_slices_and_matching_counts(app):
    with app.app_context():
        company = repo.get_main_company()
        project_id = repo.create_project(
            {"company_id": company["id"], "name": "分页仓储测试"}
        )
        category_id = _leaf_id("五金辅材及工具")
        created_ids = []
        for index in range(7):
            created_ids.append(repo.create_voucher({
                "project_id": project_id,
                "voucher_date": "2026-07-10",
                "transaction_type": "支出",
                "category_id": category_id,
                "amount": index + 1,
                "notes": f"分页记录-{index}",
                "payment_status": "未支付",
                "review_status": "待复核" if index < 6 else "已确认",
            }))

        page = repo.list_vouchers(
            project_id=project_id,
            review_status="待复核",
            limit=3,
            offset=2,
        )
        total = repo.count_vouchers(
            project_id=project_id,
            review_status="待复核",
        )

    assert [row["id"] for row in page] == list(reversed(created_ids[:6]))[2:5]
    assert total == 6


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
