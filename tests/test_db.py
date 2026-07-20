from __future__ import annotations

from construction_maintenance.db import get_db
from construction_maintenance.db import init_db


def test_init_db_creates_main_company(app):
    with app.app_context():
        init_db()
        company = get_db().execute(
            "select name, is_main from companies where is_main = 1"
        ).fetchone()

    assert company["name"] == "主公司"
    assert company["is_main"] == 1


def test_schema_contains_core_tables(app):
    with app.app_context():
        init_db()
        rows = get_db().execute(
            "select name from sqlite_master where type = 'table'"
        ).fetchall()

    table_names = {row["name"] for row in rows}
    assert {
        "companies",
        "projects",
        "vouchers",
        "expense_categories",
        "people",
        "qualifications",
        "batch_items",
        "admin_users",
        "system_settings",
    }.issubset(table_names)


def test_default_system_settings_are_seeded(app):
    with app.app_context():
        rows = get_db().execute(
            "select key, value from system_settings order by key"
        ).fetchall()

    settings = {row["key"]: row["value"] for row in rows}
    assert settings == {
        "organization_name": "工程运营管理中心",
        "session_timeout_minutes": "120",
        "support_contact": "",
        "system_name": "筑序工程运营平台",
    }


def test_legacy_system_name_is_upgraded(app):
    with app.app_context():
        get_db().execute(
            """
            update system_settings
            set value = '建筑工程维护系统'
            where key = 'system_name'
            """
        )
        get_db().commit()
        init_db()
        system_name = get_db().execute(
            "select value from system_settings where key = 'system_name'"
        ).fetchone()["value"]

    assert system_name == "筑序工程运营平台"


def test_default_expense_categories_are_seeded(app):
    with app.app_context():
        init_db()
        rows = get_db().execute(
            """
            select name, is_active
            from expense_categories
            order by sort_order, id
            """
        ).fetchall()

    assert [row["name"] for row in rows] == [
        "员工报销",
        "转账凭证",
        "材料费用",
        "油费",
        "电费",
        "人工工资",
        "其它",
    ]
    assert all(row["is_active"] == 1 for row in rows)


def test_people_table_has_id_card_attachment_column(app):
    with app.app_context():
        init_db()
        rows = get_db().execute("pragma table_info(people)").fetchall()

    column_names = {row["name"] for row in rows}
    assert "id_card_path" in column_names


def test_init_db_normalizes_legacy_batch_status(app):
    with app.app_context():
        get_db().execute(
            """
            insert into batch_items (item_type, source_filename, status)
            values ('voucher', 'old.png', '乱码状态')
            """
        )
        get_db().commit()
        init_db()
        item = get_db().execute(
            "select status from batch_items where source_filename = 'old.png'"
        ).fetchone()

    assert item["status"] == "待确认"


def test_contracts_table_initialization(app):
    with app.app_context():
        init_db()
        db_conn = get_db()
        # 验证表存在且字段正确
        cursor = db_conn.execute("pragma table_info(contracts)")
        columns = {row["name"]: row["type"] for row in cursor.fetchall()}
        assert "id" in columns
        assert "project_id" in columns
        assert "name" in columns
        assert "contract_type" in columns
        assert "attachment_path" in columns
        assert "notes" in columns
        assert "created_at" in columns
        
        # 验证外键约束
        fk_cursor = db_conn.execute("pragma foreign_key_list(contracts)")
        fk_list = fk_cursor.fetchall()
        assert len(fk_list) > 0
        assert any(row["table"] == "projects" and row["from"] == "project_id" for row in fk_list)

