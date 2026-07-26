from __future__ import annotations

from collections import defaultdict
from datetime import date

from construction_maintenance import repositories as repo
from construction_maintenance.db import get_db


def build_dashboard() -> dict:
    current_month = date.today().strftime("%Y-%m")
    vouchers = repo.list_vouchers()
    batch_items = repo.list_batch_items()
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
    # 计算每月总支出趋势与科目构成分布
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
        category_name = row["secondary_category"] or row["voucher_type"]
        by_project[row["project_name"]] += signed_amount
        by_type[category_name] += signed_amount
        
        # 提取月份 YYYY-MM
        v_date = row["voucher_date"]
        if v_date and len(v_date) >= 7:
            m_key = v_date[:7]
            months_set.add(m_key)
            categories_set.add(category_name)
            monthly_category_spend[m_key][category_name] += signed_amount
            
    # 按时间升序排列月份
    sorted_months = sorted(list(months_set))
    
    # 使用后台维护的科目顺序，保证图表配色与图例一致。
    standard_categories = repo.list_expense_category_names(include_inactive=True)
    active_categories = [c for c in standard_categories if c in categories_set]
    for c in categories_set:
        if c not in active_categories:
            active_categories.append(c)
            
    # 构造前端 Chart.js 堆叠图的数据集
    monthly_datasets = []
    for cat in active_categories:
        cat_data = []
        for m in sorted_months:
            cat_data.append(monthly_category_spend[m][cat])
        monthly_datasets.append({
            "category": cat,
            "data": cat_data
        })

    # 动态计算 30 天内临期的企业资质证书数量
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

    return {
        "month_spending": month_spending,
        "expense": expense,
        "expense_reduction": expense_reduction,
        "net_expense": net_expense,
        "income": income,
        "fund_transfer": fund_transfer,
        "total_spending": net_expense,
        "voucher_count": len(vouchers),
        "pending_count": sum(1 for row in batch_items if row["status"] == "待确认"),
        "expiring_qualifications": expiring_count,
        "by_project": sorted(by_project.items(), key=lambda item: item[1], reverse=True),
        "by_type": sorted(by_type.items(), key=lambda item: item[1], reverse=True),
        "monthly_trend": {
            "months": sorted_months,
            "datasets": monthly_datasets
        }
    }
