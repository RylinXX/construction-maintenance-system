import json
import re
from html import unescape
from urllib.parse import parse_qs, urlsplit

import pytest

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


def test_ledgers_paginate_on_server_and_summarize_all_filtered_entries(client, app):
    project_id = create_project(app, "服务端分页测试")
    target = category(app, "五金辅材及工具")
    for index in range(31):
        create_entry(
            app,
            project_id,
            amount=10,
            notes=f"SERVER_PAGE_{index:02d}",
        )
    create_entry(
        app,
        project_id,
        transaction_type="收入",
        category_id=int(category(app, "废料处置收入")["id"]),
        amount=999,
        notes="SERVER_PAGE_NONMATCH",
        payment_status="已支付/已报销",
        review_status="已确认",
    )

    for path, paginator_key in (
        ("/vouchers", "global-ledger-body"),
        (f"/projects/{project_id}/vouchers", "project-ledger-body"),
    ):
        query = (
            f"transaction_type=支出&primary_category_id={target['parent_id']}"
            f"&category_id={target['id']}&payment_status=未支付"
            "&review_status=待复核&date_from=2026-07-01"
            "&date_to=2026-07-31&per_page=15"
        )
        if path == "/vouchers":
            query += f"&project_id={project_id}"
        response = client.get(
            f"{path}?{query}"
        )
        text = response.get_data(as_text=True)

        assert response.status_code == 200
        assert text.count('class="ledger-row') == 15
        assert "31 条筛选结果" in text
        assert 'data-kpi="entry-count">31<' in text
        assert "¥310.00" in text
        assert "SERVER_PAGE_NONMATCH" not in text
        assert f"window.paginators['{paginator_key}']" not in text

        next_links = []
        export_links = []
        for href in re.findall(r'href="([^"]+)"', text):
            decoded = unescape(href)
            parsed = urlsplit(decoded)
            link_query = parse_qs(parsed.query)
            if link_query.get("page") == ["2"]:
                next_links.append(link_query)
            if parsed.path == "/exports/project-ledger":
                export_links.append(link_query)
        assert next_links
        expected_filters = {
            "transaction_type": ["支出"],
            "primary_category_id": [str(target["parent_id"])],
            "category_id": [str(target["id"])],
            "payment_status": ["未支付"],
            "review_status": ["待复核"],
            "date_from": ["2026-07-01"],
            "date_to": ["2026-07-31"],
        }
        if path == "/vouchers":
            expected_filters["project_id"] = [str(project_id)]
        assert any(
            all(link.get(key) == value for key, value in expected_filters.items())
            and link.get("per_page") == ["15"]
            for link in next_links
        )
        assert any(
            all(link.get(key) == value for key, value in expected_filters.items())
            for link in export_links
        )


@pytest.mark.parametrize(
    "query",
    ["page=0", "page=bad", "per_page=0", "per_page=24", "per_page=101"],
)
def test_ledger_rejects_invalid_pagination_parameters(client, query):
    response = client.get(f"/vouchers?{query}")

    assert response.status_code == 400
    assert "页".encode() in response.data


def test_ledger_clamps_page_above_filtered_result_range(client, app):
    project_id = create_project(app, "分页上限测试")
    for index in range(17):
        create_entry(app, project_id, notes=f"CLAMP_PAGE_{index:02d}")

    response = client.get(
        f"/projects/{project_id}/vouchers?page=999&per_page=15"
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert text.count('class="ledger-row') == 2
    assert "第 2 / 2 页" in text
    assert "CLAMP_PAGE_00" in text


def test_pending_queue_paginates_on_server_and_preserves_filters(client, app):
    project_id = create_project(app, "待补录分页测试")
    category_id = int(category(app, "运输车辆台班")["id"])
    with app.app_context():
        for index in range(31):
            repo.create_ledger_pending_item({
                "project_id": project_id,
                "item_date": "2026-03-17",
                "summary": f"PENDING_PAGE_{index:02d}",
                "suggested_category_id": category_id,
                "source_filename": "source.xls",
                "source_sheet": "汇总",
                "source_row": index + 1,
                "issue_type": "缺少金额",
            })

    default_page = client.get(
        f"/ledger-pending?project_id={project_id}&status=待补录"
    ).get_data(as_text=True)
    assert default_page.count('class="pending-item"') == 15
    assert "第 1 / 3 页，共 31 条" in default_page

    response = client.get(
        f"/ledger-pending?project_id={project_id}&status=待补录&per_page=15"
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert text.count('class="pending-item"') == 15
    assert "31 条当前结果" in text
    assert "第 1 / 3 页，共 31 条" in text
    assert "PENDING_PAGE_00" in text
    assert "PENDING_PAGE_15" not in text

    next_links = []
    for href in re.findall(r'href="([^"]+)"', text):
        parsed = urlsplit(unescape(href))
        link_query = parse_qs(parsed.query)
        if parsed.path == "/ledger-pending" and link_query.get("page") == ["2"]:
            next_links.append(link_query)
    assert any(
        link.get("project_id") == [str(project_id)]
        and link.get("status") == ["待补录"]
        and link.get("per_page") == ["15"]
        for link in next_links
    )

    final_page = client.get(
        f"/ledger-pending?project_id={project_id}&status=待补录"
        "&per_page=15&page=3"
    ).get_data(as_text=True)
    assert final_page.count('class="pending-item"') == 1
    assert "第 3 / 3 页，共 31 条" in final_page
    assert "PENDING_PAGE_30" in final_page


def test_pending_queue_rejects_invalid_pagination_parameters(client):
    response = client.get("/ledger-pending?page=0")

    assert response.status_code == 400
    assert "页码必须是正整数".encode() in response.data


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


def test_edit_voucher_preserves_import_provenance(client, app):
    project_id = create_project(app, "导入来源保留测试")
    voucher_id = create_entry(
        app,
        project_id,
        entry_user="导入操作员",
        source_record_id="SOURCE-ROW-001",
        source_filename="ledger-source.xlsx",
        source_sheet="费用明细",
        source_row=27,
        classification_confidence="高",
        original_notes="导入前原始事项",
    )
    category_id = int(category(app, "五金辅材及工具")["id"])

    response = client.post(
        f"/vouchers/{voucher_id}/edit",
        data={
            "project_id": project_id,
            "voucher_date": "2026-07-11",
            "transaction_type": "支出",
            "category_id": category_id,
            "amount": "125",
            "notes": "人工修正事项",
            "handler_name": "经办人",
            "payment_status": "未支付",
            "review_status": "已确认",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        voucher = repo.get_voucher(voucher_id)
        assert voucher["entry_user"] == "导入操作员"
        assert voucher["source_record_id"] == "SOURCE-ROW-001"
        assert voucher["source_filename"] == "ledger-source.xlsx"
        assert voucher["source_sheet"] == "费用明细"
        assert voucher["source_row"] == 27
        assert voucher["classification_confidence"] == "高"
        assert voucher["original_notes"] == "导入前原始事项"


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


def test_pending_item_ignore_persists_once_without_creating_voucher(client, app):
    _project_id, item_id, _category_id = seed_pending_item(app)

    response = client.post(f"/ledger-pending/{item_id}/ignore")

    assert response.status_code == 302
    with app.app_context():
        item = repo.get_ledger_pending_item(item_id)
        voucher_count = get_db().execute("select count(*) from vouchers").fetchone()[0]
        matching_audits = [
            row for row in repo.list_audit_events()
            if row["action"] == "ignore"
            and row["entity_type"] == "ledger_pending_item"
            and row["entity_id"] == item_id
        ]
    assert item["status"] == "已忽略"
    assert voucher_count == 0
    assert len(matching_audits) == 1

    repeated = client.post(f"/ledger-pending/{item_id}/ignore")
    assert repeated.status_code == 400
    assert "只有待补录事项可以忽略".encode() in repeated.data
    with app.app_context():
        matching_audits = [
            row for row in repo.list_audit_events()
            if row["action"] == "ignore"
            and row["entity_type"] == "ledger_pending_item"
            and row["entity_id"] == item_id
        ]
    assert len(matching_audits) == 1


def test_category_management_rejects_deleting_referenced_category(client, app):
    # Create project and voucher referencing category
    client.post("/projects", data={"name": "测试项目"})
    category_id = int(category(app, "五金辅材及工具")["id"])
    client.post(
        "/vouchers",
        data={
            "project_id": "1",
            "voucher_date": "2026-05-29",
            "transaction_type": "支出",
            "category_id": str(category_id),
            "amount": "1000",
            "payment_status": "已支付/已报销",
            "notes": "测试支出",
        },
    )

    delete_response = client.post(
        f"/expense-categories/{category_id}/delete",
        follow_redirects=True,
    )
    assert delete_response.status_code == 200
    assert "分类已被财务明细使用，不能删除".encode("utf-8") in delete_response.data




def test_category_route_rejects_root_scope_change_with_children(client, app):
    with app.app_context():
        root = get_db().execute(
            "select * from expense_categories where name = '材料费'"
        ).fetchone()

    response = client.post(
        f"/expense-categories/{root['id']}/edit",
        data={
            "name": root["name"],
            "parent_id": "",
            "transaction_scope": "收入",
            "sort_order": root["sort_order"],
            "is_active": "1",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "一级分类仍有二级分类，不能修改收支范围".encode() in response.data
    with app.app_context():
        unchanged = get_db().execute(
            "select transaction_scope from expense_categories where id = ?",
            (root["id"],),
        ).fetchone()
        assert unchanged["transaction_scope"] == "支出"


@pytest.mark.parametrize(
    ("parent_name", "deactivate_parent", "transaction_scope", "message"),
    [
        ("五金辅材及工具", False, "支出", "所属分类必须是启用的一级分类"),
        ("材料费", True, "支出", "所属分类必须是启用的一级分类"),
        ("材料费", False, "收入", "分类与收支范围不匹配"),
    ],
)
def test_category_route_rejects_forged_parent_and_scope(
    client,
    app,
    parent_name,
    deactivate_parent,
    transaction_scope,
    message,
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

    response = client.post(
        "/expense-categories",
        data={
            "name": f"路由伪造分类-{parent_name}",
            "parent_id": str(parent["id"]),
            "transaction_scope": transaction_scope,
            "sort_order": "999",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert message.encode() in response.data
    with app.app_context():
        created = get_db().execute(
            "select count(*) from expense_categories where name = ?",
            (f"路由伪造分类-{parent_name}",),
        ).fetchone()[0]
        assert created == 0


def test_category_create_rejects_invalid_parent_id_without_mutation(client, app):
    with app.app_context():
        before = [
            tuple(row)
            for row in get_db().execute(
                """
                select id, name, parent_id, transaction_scope, sort_order, is_active
                from expense_categories order by id
                """
            )
        ]

    response = client.post(
        "/expense-categories",
        data={
            "name": "非法父分类创建测试",
            "parent_id": "not-an-id",
            "transaction_scope": "支出",
            "sort_order": "999",
        },
    )

    assert response.status_code == 400
    assert "所属分类编号必须是整数".encode() in response.data
    with app.app_context():
        after = [
            tuple(row)
            for row in get_db().execute(
                """
                select id, name, parent_id, transaction_scope, sort_order, is_active
                from expense_categories order by id
                """
            )
        ]
    assert after == before


def test_category_edit_rejects_invalid_parent_id_without_mutation(client, app):
    with app.app_context():
        leaf = get_db().execute(
            "select * from expense_categories where name = '五金辅材及工具'"
        ).fetchone()
        before = tuple(leaf)

    response = client.post(
        f"/expense-categories/{leaf['id']}/edit",
        data={
            "name": leaf["name"],
            "parent_id": "not-an-id",
            "transaction_scope": leaf["transaction_scope"],
            "sort_order": str(leaf["sort_order"]),
            "is_active": "1",
        },
    )

    assert response.status_code == 400
    assert "所属分类编号必须是整数".encode() in response.data
    with app.app_context():
        after = tuple(get_db().execute(
            "select * from expense_categories where id = ?",
            (leaf["id"],),
        ).fetchone())
    assert after == before


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
