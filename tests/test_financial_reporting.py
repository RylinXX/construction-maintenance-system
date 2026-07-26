from openpyxl import load_workbook

from construction_maintenance import repositories as repo
from construction_maintenance.db import get_db
from construction_maintenance.services.dashboard import build_dashboard
from construction_maintenance.services.exports import build_project_ledger_workbook


EXPECTED_HEADERS = [
    "记录编号", "日期", "项目", "收支类型", "一级分类", "二级分类",
    "事项摘要", "金额", "经办/垫付人", "付款状态", "付款日期",
    "支付/报销说明", "复核状态", "分类置信度", "来源文件",
    "来源工作表", "原始行号", "作废状态",
]


def _leaf_id(name: str) -> int:
    return int(get_db().execute(
        "select id from expense_categories where name = ? and parent_id is not null",
        (name,),
    ).fetchone()["id"])


def seed_financial_entries():
    company = repo.get_main_company()
    project_id = repo.create_project({
        "company_id": company["id"],
        "name": "财务口径测试项目",
    })
    rows = [
        ("支出", "材料运输费", 1000),
        ("冲减支出", "材料运输费", 100),
        ("收入", "废料处置收入", 50),
        ("资金往来", "备用金", 200),
    ]
    for index, (transaction_type, category, amount) in enumerate(rows, start=1):
        repo.create_voucher({
            "project_id": project_id,
            "voucher_date": "2026-07-01",
            "transaction_type": transaction_type,
            "category_id": _leaf_id(category),
            "amount": amount,
            "notes": "测试事项",
            "source_record_id": f"REPORT-{index}",
            "source_filename": "=HYPERLINK(\"https://invalid\")" if index == 1 else "source.xls",
            "source_sheet": "汇总",
            "source_row": index,
            "payment_status": "未支付",
        })
    return project_id


def test_dashboard_uses_transaction_aware_financial_totals(app):
    with app.app_context():
        seed_financial_entries()
        dashboard = build_dashboard()

    assert dashboard["expense"] == 1000
    assert dashboard["expense_reduction"] == 100
    assert dashboard["net_expense"] == 900
    assert dashboard["income"] == 50
    assert dashboard["fund_transfer"] == 200


def test_project_ledger_export_contains_structured_fields_and_escapes_formulas(
    app, tmp_path
):
    with app.app_context():
        seed_financial_entries()
        output = build_project_ledger_workbook(tmp_path / "ledger.xlsx")

    sheet = load_workbook(output).active
    assert [cell.value for cell in sheet[1]] == EXPECTED_HEADERS
    assert "'=HYPERLINK(\"https://invalid\")" in [
        sheet.cell(row=row, column=15).value for row in range(2, sheet.max_row + 1)
    ]
    assert sheet.freeze_panes == "A2"
    assert sheet.auto_filter.ref == f"A1:R{sheet.max_row}"
