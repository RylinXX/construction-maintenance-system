from __future__ import annotations

from collections import defaultdict
from datetime import date

from construction_maintenance import repositories as repo


def build_dashboard() -> dict:
    current_month = date.today().strftime("%Y-%m")
    vouchers = repo.list_vouchers()
    batch_items = repo.list_batch_items()
    total_spending = sum(float(row["amount"]) for row in vouchers)
    month_spending = sum(
        float(row["amount"]) for row in vouchers if str(row["voucher_date"]).startswith(current_month)
    )
    by_project: dict[str, float] = defaultdict(float)
    by_type: dict[str, float] = defaultdict(float)
    for row in vouchers:
        by_project[row["project_name"]] += float(row["amount"])
        by_type[row["voucher_type"]] += float(row["amount"])
    return {
        "month_spending": month_spending,
        "total_spending": total_spending,
        "voucher_count": len(vouchers),
        "pending_count": sum(1 for row in batch_items if row["status"] == "待确认"),
        "expiring_qualifications": 0,
        "by_project": sorted(by_project.items(), key=lambda item: item[1], reverse=True),
        "by_type": sorted(by_type.items(), key=lambda item: item[1], reverse=True),
    }
