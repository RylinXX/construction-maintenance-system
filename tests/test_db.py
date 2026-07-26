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
        "system_name": "营力特数字化系统",
    }


def test_legacy_system_names_are_upgraded(app):
    with app.app_context():
        for legacy_name in ("建筑工程维护系统", "筑序工程运营平台"):
            get_db().execute(
                """
                update system_settings
                set value = ?
                where key = 'system_name'
                """,
                (legacy_name,),
            )
            get_db().commit()
            init_db()
            system_name = get_db().execute(
                "select value from system_settings where key = 'system_name'"
            ).fetchone()["value"]
            assert system_name == "营力特数字化系统"


def test_structured_expense_categories_replace_legacy_defaults(app):
    with app.app_context():
        init_db()
        roots = get_db().execute(
            """
            select name, transaction_scope
            from expense_categories
            where parent_id is null and is_active = 1
            order by sort_order, id
            """
        ).fetchall()
        active_legacy_count = get_db().execute(
            """
            select count(*)
            from expense_categories
            where name in ('员工报销', '转账凭证', '材料费用', '油费', '人工工资', '其它')
              and is_active = 1
            """
        ).fetchone()[0]

    assert [row["name"] for row in roots] == [
        "人工成本",
        "商务及前期费",
        "安全文明施工费",
        "机械设备费",
        "材料费",
        "燃料动力费",
        "财务及其他",
        "车辆费用",
        "运输及处置费",
        "项目现场管理费",
        "收入",
        "资金往来",
    ]
    assert {row["transaction_scope"] for row in roots} == {"支出", "收入", "资金往来"}
    assert active_legacy_count == 0


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
