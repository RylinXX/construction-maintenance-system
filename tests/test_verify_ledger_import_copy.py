from pathlib import Path

from construction_maintenance.db import get_db
from scripts.verify_ledger_import_copy import EXPECTED, PROTECTED_TABLES, table_counts


ROOT = Path(__file__).resolve().parents[1]


def test_copy_verifier_uses_approved_acceptance_contract(app):
    assert PROTECTED_TABLES == (
        "companies",
        "people",
        "qualifications",
        "attendance",
        "salary_payments",
        "salary_sheets",
        "admin_users",
        "system_settings",
    )
    assert EXPECTED == {
        "projects": 6,
        "entries": 4907,
        "review_entries": 483,
        "pending_items": 276,
        "expense": 11_643_311.78,
        "expense_reduction": 17_573.0,
        "net_expense": 11_625_738.78,
        "income": 43_670.0,
        "fund_transfer": 50_128.83,
    }

    with app.app_context():
        counts = table_counts(get_db())
    assert set(counts) == set(PROTECTED_TABLES)
    assert all(isinstance(value, int) for value in counts.values())


def test_nginx_example_has_import_and_proxy_limits():
    config = (ROOT / "deploy/nginx-pam.conf.example").read_text(encoding="utf-8")

    assert "ssl_protocols TLSv1.2 TLSv1.3;" in config
    assert "client_max_body_size 20m;" in config
    assert "proxy_connect_timeout 60s;" in config
    assert "proxy_send_timeout 120s;" in config
    assert "proxy_read_timeout 120s;" in config
