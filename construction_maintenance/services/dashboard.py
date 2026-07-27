from __future__ import annotations

from collections import defaultdict
from datetime import date

from construction_maintenance import repositories as repo
from construction_maintenance.db import get_db


def build_dashboard() -> dict:
    current_month = date.today().strftime("%Y-%m")
    vouchers = repo.list_vouchers()
    batch_items = repo.list_batch_items()
    projects = repo.list_projects()
    
    financial = get_db().execute(
        """
        select
          coalesce(sum(case when transaction_type = '支出' then amount else 0 end), 0) as expense,
          coalesce(sum(case when transaction_type = '冲减支出' then amount else 0 end), 0) as expense_reduction,
          coalesce(sum(case when transaction_type = '收入' then amount else 0 end), 0) as income,
          coalesce(sum(case when transaction_type = '资金往来' then amount else 0 end), 0) as fund_transfer
        from vouchers
        where is_void = 0
        """
    ).fetchone()
    
    month_row = get_db().execute(
        """
        select coalesce(sum(case
          when transaction_type = '支出' then amount
          when transaction_type = '冲减支出' then -amount
          else 0 end), 0) as net_expense
        from vouchers
        where is_void = 0 and voucher_date like ?
        """,
        (f"{current_month}%",),
    ).fetchone()
    
    expense = float(financial["expense"])
    expense_reduction = float(financial["expense_reduction"])
    net_expense = expense - expense_reduction
    income = float(financial["income"])
    fund_transfer = float(financial["fund_transfer"])
    month_spending = float(month_row["net_expense"])
    
    by_project: dict[str, float] = defaultdict(float)
    by_type: dict[str, float] = defaultdict(float)
    by_primary_type: dict[str, float] = defaultdict(float)
    
    # Structure: by_project_categories[project_name][category_name] = amount
    by_project_categories: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    
    months_set = set()
    categories_set = set()
    monthly_category_spend = defaultdict(lambda: defaultdict(float))
    
    for row in vouchers:
        transaction_type = row["transaction_type"]
        if transaction_type not in {"支出", "冲减支出"}:
            continue
        signed_amount = float(row["amount"])
        if transaction_type == "冲减支出":
            signed_amount = -signed_amount
            
        p_name = row["project_name"]
        cat_name = row["secondary_category"] or row["voucher_type"] or "其他"
        primary_cat = row["primary_category"] or "其他支出"
        
        by_project[p_name] += signed_amount
        by_type[cat_name] += signed_amount
        by_primary_type[primary_cat] += signed_amount
        
        # Per project category grouping
        by_project_categories[p_name][primary_cat] += signed_amount
        by_project_categories["ALL"][primary_cat] += signed_amount
        
        # Extract YYYY-MM
        v_date = row["voucher_date"]
        if v_date and len(v_date) >= 7:
            m_key = v_date[:7]
            months_set.add(m_key)
            categories_set.add(primary_cat)
            monthly_category_spend[m_key][primary_cat] += signed_amount
            
    sorted_months = sorted(list(months_set))
    
    # Years for filtering
    years_set = sorted(list({m[:4] for m in sorted_months}), reverse=True)
    recent_12_months = sorted_months[-12:] if len(sorted_months) > 12 else sorted_months
    
    standard_categories = repo.list_expense_category_names(include_inactive=True)
    active_categories = [c for c in standard_categories if c in categories_set]
    for c in categories_set:
        if c not in active_categories:
            active_categories.append(c)
            
    monthly_datasets = []
    for cat in active_categories:
        cat_data = []
        for m in sorted_months:
            cat_data.append(round(monthly_category_spend[m][cat], 2))
        monthly_datasets.append({
            "category": cat,
            "data": cat_data
        })

    # Qualifications expiring in 30 days
    qualifications = repo.list_qualifications()
    expiring_count = 0
    today = date.today()
    for q in qualifications:
        if not q["is_long_term"] and q["expiry_date"]:
            try:
                exp_date = date.fromisoformat(q["expiry_date"])
                delta = (exp_date - today).days
                if 0 <= delta <= 30:
                    expiring_count += 1
            except (ValueError, TypeError):
                pass

    # Pending items count (both OCR batch queue and ledger pending queue)
    pending_batch = sum(1 for row in batch_items if row["status"] == "待确认")
    pending_ledger = len(repo.list_ledger_pending_items(status="待补录"))
    pending_count = pending_batch + pending_ledger

    # Convert by_project_categories to regular dict for json serialization in template
    project_cat_dict = {}
    for p_key, cat_map in by_project_categories.items():
        project_cat_dict[p_key] = [
            {"name": k, "value": round(v, 2)}
            for k, v in sorted(cat_map.items(), key=lambda x: x[1], reverse=True)
            if v > 0
        ]

    return {
        "month_spending": month_spending,
        "expense": expense,
        "expense_reduction": expense_reduction,
        "net_expense": net_expense,
        "income": income,
        "fund_transfer": fund_transfer,
        "total_spending": net_expense,
        "voucher_count": len(vouchers),
        "pending_count": pending_count,
        "expiring_qualifications": expiring_count,
        "by_project": sorted(by_project.items(), key=lambda item: item[1], reverse=True),
        "by_type": sorted(by_type.items(), key=lambda item: item[1], reverse=True),
        "by_primary_type": sorted(by_primary_type.items(), key=lambda item: item[1], reverse=True),
        "by_project_categories": project_cat_dict,
        "projects_list": [p["name"] for p in projects],
        "monthly_trend": {
            "months": sorted_months,
            "recent_12_months": recent_12_months,
            "years": years_set,
            "datasets": monthly_datasets
        }
    }
