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
        "people",
        "qualifications",
        "batch_items",
    }.issubset(table_names)
