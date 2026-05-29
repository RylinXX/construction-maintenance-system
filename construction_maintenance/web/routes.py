from __future__ import annotations

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from construction_maintenance import repositories as repo
from construction_maintenance.web.forms import required_text
from construction_maintenance.web.forms import text_value

bp = Blueprint("web", __name__)


@bp.app_template_filter("money")
def money(value: float) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


@bp.get("/")
def dashboard():
    vouchers = repo.list_vouchers()
    total = sum(float(row["amount"]) for row in vouchers)
    metrics = {
        "month_spending": f"{total:.2f}",
        "total_spending": f"{total:.2f}",
        "voucher_count": len(vouchers),
        "pending_count": 0,
        "expiring_qualifications": 0,
    }
    return render_template("dashboard.html", metrics=metrics)


@bp.route("/projects", methods=["GET", "POST"])
def projects():
    if request.method == "POST":
        main_company = repo.get_main_company()
        repo.create_project(
            {
                "company_id": main_company["id"],
                "name": required_text(request.form, "name", "项目名称"),
                "status": text_value(request.form, "status") or "进行中",
                "owner": text_value(request.form, "owner"),
                "start_date": text_value(request.form, "start_date"),
                "end_date": text_value(request.form, "end_date"),
                "notes": text_value(request.form, "notes"),
            }
        )
        return redirect(url_for("web.projects"))
    return render_template("projects.html", projects=repo.list_projects())


@bp.route("/vouchers", methods=["GET", "POST"])
def vouchers():
    if request.method == "POST":
        repo.create_voucher(
            {
                "project_id": int(required_text(request.form, "project_id", "项目")),
                "voucher_date": required_text(request.form, "voucher_date", "日期"),
                "voucher_type": required_text(request.form, "voucher_type", "凭证类型"),
                "amount": required_text(request.form, "amount", "金额"),
                "notes": text_value(request.form, "notes"),
                "attachment_path": "",
                "entry_user": text_value(request.form, "entry_user"),
            }
        )
        return redirect(url_for("web.vouchers"))
    return render_template(
        "vouchers.html",
        projects=repo.list_projects(),
        vouchers=repo.list_vouchers(),
        voucher_types=["员工报销", "转账凭证", "材料费用", "油费", "电费", "人工工资", "其它"],
    )


@bp.route("/people", methods=["GET", "POST"])
def people():
    if request.method == "POST":
        repo.create_person(
            {
                "name": required_text(request.form, "name", "姓名"),
                "id_number": required_text(request.form, "id_number", "身份证号"),
                "gender": text_value(request.form, "gender"),
                "birth_date": text_value(request.form, "birth_date"),
                "age": int(text_value(request.form, "age") or 0) or None,
                "phone": text_value(request.form, "phone"),
                "address": text_value(request.form, "address"),
                "job_type": text_value(request.form, "job_type"),
                "bank_card": text_value(request.form, "bank_card"),
                "bank_name": text_value(request.form, "bank_name"),
                "entry_date": text_value(request.form, "entry_date"),
                "notes": text_value(request.form, "notes"),
            }
        )
        return redirect(url_for("web.people"))
    return render_template("people.html", people=repo.list_people())
