from __future__ import annotations

from construction_maintenance import repositories as repo
from construction_maintenance.services.dashboard import build_dashboard


def test_dashboard_counts_vouchers_and_pending_items(app):
    with app.app_context():
        company = repo.get_main_company()
        project_id = repo.create_project({"company_id": company["id"], "name": "土方工程"})
        repo.create_voucher(
            {
                "project_id": project_id,
                "voucher_date": "2026-05-29",
                "voucher_type": "油费",
                "amount": 500,
                "notes": "",
                "attachment_path": "",
                "entry_user": "",
            }
        )
        repo.create_batch_item({"item_type": "voucher", "source_filename": "pay.png"})
        dashboard = build_dashboard()

    assert dashboard["total_spending"] == 500
    assert dashboard["voucher_count"] == 1
    assert dashboard["pending_count"] == 1
