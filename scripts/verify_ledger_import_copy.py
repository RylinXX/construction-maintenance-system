from __future__ import annotations

import argparse
import json
from pathlib import Path

from construction_maintenance import create_app
from construction_maintenance.db import get_db
from construction_maintenance.services.ledger_import import (
    apply_ledger_import,
    parse_ledger_source,
)


PROTECTED_TABLES = (
    "companies",
    "people",
    "qualifications",
    "attendance",
    "salary_payments",
    "salary_sheets",
    "admin_users",
    "system_settings",
)

EXPECTED = {
    "projects": 6,
    "entries": 4907,
    "review_entries": 483,
    "pending_items": 276,
    "expense": 11_643_311.78,
    "expense_reduction": 17_573.00,
    "net_expense": 11_625_738.78,
    "income": 43_670.00,
    "fund_transfer": 50_128.83,
}


def table_counts(db) -> dict[str, int]:
    return {
        table: int(db.execute(f"select count(*) from {table}").fetchone()[0])
        for table in PROTECTED_TABLES
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()

    app = create_app(
        {
            "TESTING": True,
            "AUTH_REQUIRED": False,
            "CSRF_ENABLED": False,
            "SEED_DEMO_DATA": False,
            "DATABASE": args.database,
            "UPLOAD_FOLDER": args.database.parent / "verify-uploads",
        }
    )
    preview = parse_ledger_source(args.source)

    with app.app_context():
        db = get_db()
        protected_before = table_counts(db)
        apply_ledger_import(
            preview,
            replace_demo_projects=True,
            actor_admin_id=None,
        )
        protected_after = table_counts(db)
        if protected_after != protected_before:
            raise AssertionError(
                {
                    "protected_before": protected_before,
                    "protected_after": protected_after,
                }
            )

        project_placeholders = ",".join("?" for _ in preview.project_names)
        project_count = int(
            db.execute(
                f"select count(*) from projects where name in ({project_placeholders})",
                preview.project_names,
            ).fetchone()[0]
        )
        entries = int(
            db.execute(
                """
                select count(*) from vouchers
                where source_record_id is not null and is_void = 0
                """
            ).fetchone()[0]
        )
        review_entries = int(
            db.execute(
                """
                select count(*) from vouchers
                where review_status = '待复核' and is_void = 0
                """
            ).fetchone()[0]
        )
        pending_items = int(
            db.execute(
                "select count(*) from ledger_pending_items where status = '待补录'"
            ).fetchone()[0]
        )
        transaction_amounts = {
            row["transaction_type"]: float(row["amount"])
            for row in db.execute(
                """
                select transaction_type, round(sum(amount), 2) as amount
                from vouchers
                where source_record_id is not null and is_void = 0
                group by transaction_type
                """
            ).fetchall()
        }
        expense = transaction_amounts.get("支出", 0.0)
        expense_reduction = transaction_amounts.get("冲减支出", 0.0)
        actual = {
            "projects": project_count,
            "entries": entries,
            "review_entries": review_entries,
            "pending_items": pending_items,
            "expense": expense,
            "expense_reduction": expense_reduction,
            "net_expense": expense - expense_reduction,
            "income": transaction_amounts.get("收入", 0.0),
            "fund_transfer": transaction_amounts.get("资金往来", 0.0),
        }
        if actual != EXPECTED:
            raise AssertionError({"expected": EXPECTED, "actual": actual})

        second = apply_ledger_import(
            preview,
            replace_demo_projects=True,
            actor_admin_id=None,
        )
        if second["entries"] != 0 or second["pending_items"] != 0:
            raise AssertionError({"second_import": second})

    print(
        json.dumps(
            {"protected": protected_after, "import": actual},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
