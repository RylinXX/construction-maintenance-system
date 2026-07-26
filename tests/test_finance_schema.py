from construction_maintenance.db import get_db, init_db
from construction_maintenance.finance import LEDGER_CATEGORY_TREE


def test_finance_schema_has_structured_entry_and_pending_columns(app):
    with app.app_context():
        init_db()
        db = get_db()
        voucher_columns = {
            row["name"] for row in db.execute("pragma table_info(vouchers)")
        }
        pending_columns = {
            row["name"]
            for row in db.execute("pragma table_info(ledger_pending_items)")
        }

    assert {
        "source_record_id", "transaction_type", "category_id", "handler_name",
        "payment_status", "payment_date", "payment_notes", "review_status",
        "classification_confidence", "source_filename", "source_sheet",
        "source_row", "original_notes",
    }.issubset(voucher_columns)
    assert {
        "project_id", "item_date", "summary", "suggested_category_id",
        "handler_name", "payment_notes", "source_filename", "source_sheet",
        "source_row", "issue_type", "status", "voucher_id",
    }.issubset(pending_columns)


def test_ledger_category_tree_is_seeded_idempotently(app):
    with app.app_context():
        init_db()
        init_db()
        db = get_db()
        roots = db.execute(
            "select * from expense_categories where parent_id is null and is_active = 1"
        ).fetchall()
        leaves = db.execute(
            "select * from expense_categories where parent_id is not null and is_active = 1"
        ).fetchall()

    assert len(LEDGER_CATEGORY_TREE) == 12
    assert len(roots) == 12
    assert len(leaves) == 59
    assert {row["transaction_scope"] for row in roots} == {
        "支出", "收入", "资金往来"
    }
