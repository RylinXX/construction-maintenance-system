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
    # 计算每月总支出趋势与科目构成分布
    months_set = set()
    categories_set = set()
    monthly_category_spend = defaultdict(lambda: defaultdict(float))
    
    for row in vouchers:
        by_project[row["project_name"]] += float(row["amount"])
        by_type[row["voucher_type"]] += float(row["amount"])
        
        # 提取月份 YYYY-MM
        v_date = row["voucher_date"]
        if v_date and len(v_date) >= 7:
            m_key = v_date[:7]
            months_set.add(m_key)
            categories_set.add(row["voucher_type"])
            monthly_category_spend[m_key][row["voucher_type"]] += float(row["amount"])
            
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
        "total_spending": total_spending,
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
