import json
import re

from construction_maintenance import repositories as repo
from construction_maintenance.db import get_db


def category(app, name: str):
    with app.app_context():
        return get_db().execute(
            "select id, parent_id from expense_categories where name = ?",
            (name,),
        ).fetchone()


def create_project(app, name: str) -> int:
    with app.app_context():
        return repo.create_project({
            "company_id": repo.get_main_company()["id"],
            "name": name,
        })


def create_entry(app, project_id: int, **overrides) -> int:
    payload = {
        "project_id": project_id,
        "voucher_date": "2026-07-10",
        "transaction_type": "支出",
        "category_id": int(category(app, "五金辅材及工具")["id"]),
        "amount": 100,
        "notes": "FILTER_MATCH",
        "payment_status": "未支付",
        "review_status": "待复核",
    }
    payload.update(overrides)
    with app.app_context():
        return repo.create_voucher(payload)


def seed_structured_financial_entry(app):
    with app.app_context():
        company = repo.get_main_company()
        project_id = repo.create_project({
            "company_id": company["id"], "name": "页面测试项目"
        })
        category = get_db().execute(
            """
            select leaf.id, leaf.parent_id
            from expense_categories leaf
            where leaf.name = '五金辅材及工具'
            """
        ).fetchone()
        repo.create_voucher({
            "project_id": project_id,
            "voucher_date": "2026-07-01",
            "transaction_type": "支出",
            "category_id": category["id"],
            "amount": 100,
            "payment_status": "未支付",
            "review_status": "待复核",
        })
        return {
            "project_id": project_id,
            "category_id": int(category["id"]),
            "primary_id": int(category["parent_id"]),
        }


def seed_pending_item(app):
    with app.app_context():
        company = repo.get_main_company()
        project_id = repo.create_project({
            "company_id": company["id"], "name": "待补录页面测试"
        })
        category_id = int(get_db().execute(
            "select id from expense_categories where name = '运输车辆台班'"
        ).fetchone()["id"])
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
        return project_id, item_id, category_id


def test_project_ledger_renders_structured_filters_and_summary(client, app):
    seeded = seed_structured_financial_entry(app)
    response = client.get(
        f"/projects/{seeded['project_id']}/vouchers?transaction_type=支出&payment_status=未支付"
    )
    assert response.status_code == 200
    assert "项目净支出".encode() in response.data
    assert "一级分类".encode() in response.data
    assert "未支付".encode() in response.data


def test_pending_item_can_be_completed(client, app):
    _project_id, item_id, category_id = seed_pending_item(app)
    response = client.post(
        f"/ledger-pending/{item_id}/complete",
        data={
            "amount": "1200",
            "transaction_type": "支出",
            "category_id": str(category_id),
            "payment_status": "支付状态待确认",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "已转正式明细".encode() in response.data


def test_project_ledger_filters_exclude_nonmatching_entries(client, app):
    project_id = create_project(app, "筛选排除测试")
    target = category(app, "五金辅材及工具")
    income = category(app, "废料处置收入")
    create_entry(app, project_id)
    create_entry(
        app,
        project_id,
        voucher_date="2026-06-01",
        transaction_type="收入",
        category_id=int(income["id"]),
        amount=200,
        notes="FILTER_EARLY_INCOME",
        payment_status="已支付/已报销",
        review_status="已确认",
    )
    create_entry(
        app,
        project_id,
        voucher_date="2026-08-01",
        amount=300,
        notes="FILTER_LATE_EXPENSE",
    )
    cases = [
        ("transaction_type=支出", "FILTER_EARLY_INCOME"),
        (f"primary_category_id={target['parent_id']}", "FILTER_EARLY_INCOME"),
        (f"category_id={target['id']}", "FILTER_EARLY_INCOME"),
        ("payment_status=未支付", "FILTER_EARLY_INCOME"),
        ("review_status=待复核", "FILTER_EARLY_INCOME"),
        ("date_from=2026-07-01", "FILTER_EARLY_INCOME"),
        ("date_to=2026-07-31", "FILTER_LATE_EXPENSE"),
    ]
    for query, excluded_marker in cases:
        response = client.get(f"/projects/{project_id}/vouchers?{query}")
        assert response.status_code == 200
        assert b"FILTER_MATCH" in response.data
        assert excluded_marker.encode() not in response.data


def test_global_ledger_filters_exclude_nonmatching_entries(client, app):
    project_id = create_project(app, "全局筛选目标项目")
    other_project_id = create_project(app, "全局筛选其他项目")
    target = category(app, "五金辅材及工具")
    income = category(app, "废料处置收入")
    create_entry(app, project_id)
    create_entry(
        app,
        project_id,
        voucher_date="2026-06-01",
        transaction_type="收入",
        category_id=int(income["id"]),
        notes="GLOBAL_EARLY_INCOME",
        payment_status="已支付/已报销",
        review_status="已确认",
    )
    create_entry(
        app,
        project_id,
        voucher_date="2026-08-01",
        notes="GLOBAL_LATE_EXPENSE",
    )
    create_entry(app, other_project_id, notes="GLOBAL_OTHER_PROJECT")

    cases = [
        (f"project_id={project_id}", "GLOBAL_OTHER_PROJECT"),
        ("transaction_type=支出", "GLOBAL_EARLY_INCOME"),
        (f"primary_category_id={target['parent_id']}", "GLOBAL_EARLY_INCOME"),
        (f"category_id={target['id']}", "GLOBAL_EARLY_INCOME"),
        ("payment_status=未支付", "GLOBAL_EARLY_INCOME"),
        ("review_status=待复核", "GLOBAL_EARLY_INCOME"),
        ("date_from=2026-07-01", "GLOBAL_EARLY_INCOME"),
        ("date_to=2026-07-31", "GLOBAL_LATE_EXPENSE"),
    ]
    for query, excluded_marker in cases:
        response = client.get(f"/vouchers?{query}")
        assert response.status_code == 200
        assert b"FILTER_MATCH" in response.data
        assert excluded_marker.encode() not in response.data


def test_global_ledger_renders_approved_kpis(client, app):
    project_id = create_project(app, "全局指标测试")
    create_entry(app, project_id, amount=1000, notes="支出指标")
    create_entry(
        app,
        project_id,
        transaction_type="冲减支出",
        amount=100,
        notes="冲减指标",
    )
    create_entry(
        app,
        project_id,
        transaction_type="收入",
        category_id=int(category(app, "废料处置收入")["id"]),
        amount=50,
        notes="收入指标",
        payment_status="已支付/已报销",
    )
    create_entry(
        app,
        project_id,
        transaction_type="资金往来",
        category_id=int(category(app, "备用金")["id"]),
        amount=200,
        notes="资金指标",
        payment_status="已支付/已报销",
    )

    response = client.get("/vouchers")

    assert response.status_code == 200
    for label in (
        "支出原额",
        "冲减支出",
        "净支出",
        "收入",
        "资金往来",
        "未结金额",
        "记录数",
    ):
        assert label.encode() in response.data
    assert b'data-kpi="entry-count">4<' in response.data


def test_voucher_route_requires_structured_category(client, app):
    project_id = create_project(app, "结构化写入测试")
    response = client.post(
        "/vouchers",
        data={
            "project_id": project_id,
            "voucher_date": "2026-07-10",
            "transaction_type": "支出",
            "voucher_type": "材料费用",
            "amount": "100",
            "payment_status": "未支付",
        },
    )
    assert response.status_code == 400
    assert "二级分类不能为空".encode() in response.data
    with app.app_context():
        assert repo.list_vouchers(project_id=project_id) == []


def test_edit_voucher_can_move_entry_to_another_project(client, app):
    source_project_id = create_project(app, "原项目")
    target_project_id = create_project(app, "调整后项目")
    category_id = int(category(app, "五金辅材及工具")["id"])
    voucher_id = create_entry(app, source_project_id)

    response = client.post(
        f"/vouchers/{voucher_id}/edit",
        data={
            "project_id": target_project_id,
            "voucher_date": "2026-07-11",
            "transaction_type": "支出",
            "category_id": category_id,
            "amount": "125",
            "payment_status": "未支付",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        voucher = repo.get_voucher(voucher_id)
        assert voucher["project_id"] == target_project_id


def test_global_ledger_edit_form_exposes_project_selector(client, app):
    project_id = create_project(app, "可调整项目")
    create_entry(app, project_id)

    response = client.get("/vouchers")

    assert response.status_code == 200
    assert b'id="editProject"' in response.data
    assert b'name="project_id"' in response.data
    assert f'data-project-id="{project_id}"'.encode() in response.data


def test_pending_form_sources_categories_for_every_transaction_scope(client, app):
    _project_id, _item_id, _category_id = seed_pending_item(app)
    response = client.get("/ledger-pending")

    assert response.status_code == 200
    assert b"const pendingCategories" in response.data
    match = re.search(r"const pendingCategories = (.*);", response.get_data(as_text=True))
    assert match is not None
    names = {item["name"] for item in json.loads(match.group(1))}
    assert {"废料处置收入", "备用金"} <= names
    assert b"syncPendingCategories" in response.data


def test_category_management_does_not_offer_destructive_deletion(client, app):
    response = client.get("/expense-categories")
    assert response.status_code == 200
    assert b"/delete" not in response.data

    category_id = int(category(app, "五金辅材及工具")["id"])
    delete_response = client.post(f"/expense-categories/{category_id}/delete")
    assert delete_response.status_code == 404


def test_route_rejects_category_scope_mismatch(client, app):
    seeded = seed_structured_financial_entry(app)
    response = client.post(
        "/vouchers",
        data={
            "project_id": seeded["project_id"],
            "voucher_date": "2026-07-02",
            "transaction_type": "收入",
            "category_id": seeded["category_id"],
            "amount": "50",
            "payment_status": "已支付/已报销",
        },
    )
    assert response.status_code == 400
    assert "分类与收支类型不匹配".encode() in response.data


def test_route_rejects_inactive_leaf(client, app):
    seeded = seed_structured_financial_entry(app)
    with app.app_context():
        get_db().execute(
            "update expense_categories set is_active = 0 where id = ?",
            (seeded["category_id"],),
        )
        get_db().commit()
    response = client.post(
        "/vouchers",
        data={
            "project_id": seeded["project_id"],
            "voucher_date": "2026-07-02",
            "transaction_type": "支出",
            "category_id": seeded["category_id"],
            "amount": "50",
            "payment_status": "未支付",
        },
    )
    assert response.status_code == 400
    assert "二级分类不存在或已停用".encode() in response.data


def test_category_migration_route_moves_existing_entry(client, app):
    seeded = seed_structured_financial_entry(app)
    with app.app_context():
        target_id = int(get_db().execute(
            "select id from expense_categories where name = '电气材料'"
        ).fetchone()["id"])
    response = client.post(
        f"/expense-categories/{seeded['category_id']}/migrate",
        data={"target_id": str(target_id)},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        source_active = get_db().execute(
            "select is_active from expense_categories where id = ?",
            (seeded["category_id"],),
        ).fetchone()["is_active"]
        voucher_category = get_db().execute(
            "select category_id from vouchers where project_id = ?",
            (seeded["project_id"],),
        ).fetchone()["category_id"]
    assert source_active == 0
    assert voucher_category == target_id
