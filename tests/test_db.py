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
    }.issubset(table_names)


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
