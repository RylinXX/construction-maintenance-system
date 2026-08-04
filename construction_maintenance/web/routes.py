from __future__ import annotations

import sqlite3
from flask import Blueprint
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask import flash, send_file
from construction_maintenance.security import authenticate_user
from construction_maintenance.security import login_user, logout_user
from construction_maintenance.security import require_admin
from construction_maintenance.security import require_super_admin
from construction_maintenance.security import safe_redirect_target
from construction_maintenance.security import get_current_admin

from construction_maintenance import repositories as repo
from construction_maintenance.finance import (
    PAYMENT_STATUSES,
    PENDING_STATUSES,
    REVIEW_STATUSES,
    TRANSACTION_TYPES,
)
from construction_maintenance.web.forms import required_text
from construction_maintenance.web.forms import optional_int
from construction_maintenance.web.forms import text_value
from construction_maintenance.services.ocr import recognize_batch_upload
from concurrent.futures import ThreadPoolExecutor
from datetime import date as date_value
import calendar
import hashlib
import time

ocr_executor = ThreadPoolExecutor(max_workers=3)


def _parse_month(value: object) -> tuple[str, int, int]:
    month = str(value or "").strip()
    try:
        year_text, month_text = month.split("-", 1)
        if len(year_text) != 4 or len(month_text) != 2:
            raise ValueError
        year, month_number = int(year_text), int(month_text)
        calendar.monthrange(year, month_number)
    except (TypeError, ValueError, calendar.IllegalMonthError) as exc:
        raise ValueError("月份格式无效，请使用 YYYY-MM") from exc
    return month, year, month_number


def _parse_iso_date(value: object, label: str = "日期") -> str:
    text = str(value or "").strip()
    try:
        date_value.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label}格式无效") from exc
    return text


def _async_ocr_worker(app, item_id: int, stored_path_str: str, item_type: str):
    from pathlib import Path
    import json
    from construction_maintenance.services.ocr import recognize_batch_upload

    with app.app_context():
        try:
            stored_path = Path(stored_path_str)
            ocr_result = recognize_batch_upload(stored_path, item_type)

            recognized_json = json.dumps(ocr_result.data, ensure_ascii=False)
            repo.update_batch_item_recognition(
                item_id,
                status=ocr_result.status,
                recognized_json=recognized_json,
                confidence=ocr_result.confidence,
            )
        except Exception as exc:
            repo.update_batch_item_recognition(
                item_id,
                status="待确认",
                recognized_json=json.dumps(
                    {"message": f"OCR 识别失败，请人工确认：{exc}"},
                    ensure_ascii=False,
                ),
                confidence=None,
            )

bp = Blueprint("web", __name__)

LEDGER_PER_PAGE_OPTIONS = (15, 25, 50, 100)


def _voucher_type_choices(project_id: int | None = None) -> list[str]:
    choices = repo.list_expense_category_names()
    for name in repo.list_voucher_type_names(project_id=project_id):
        if name not in choices:
            choices.append(name)
    return choices


def _actor_id() -> int | None:
    user = get_current_admin()
    return int(user["id"]) if user is not None else None


def _ledger_filters() -> dict:
    return {
        "transaction_type": request.args.get("transaction_type", "").strip(),
        "primary_category_id": request.args.get("primary_category_id", type=int),
        "category_id": request.args.get("category_id", type=int),
        "payment_status": request.args.get("payment_status", "").strip(),
        "review_status": request.args.get("review_status", "").strip(),
        "date_from": request.args.get("date_from", "").strip(),
        "date_to": request.args.get("date_to", "").strip(),
    }


def _ledger_pagination_params(*, default_per_page: int = 25) -> tuple[int, int]:
    page_text = request.args.get("page", "1").strip()
    per_page_text = request.args.get("per_page", str(default_per_page)).strip()
    try:
        page = int(page_text)
    except (TypeError, ValueError) as exc:
        raise ValueError("页码必须是正整数") from exc
    if page < 1:
        raise ValueError("页码必须是正整数")
    try:
        per_page = int(per_page_text)
    except (TypeError, ValueError) as exc:
        raise ValueError("每页条数无效") from exc
    if per_page not in LEDGER_PER_PAGE_OPTIONS:
        raise ValueError("每页条数必须是 15、25、50 或 100")
    return page, per_page


def _ledger_pagination_context(
    total_count: int, page: int, per_page: int
) -> dict:
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = min(page, total_pages)
    base_args = request.args.to_dict(flat=True)
    base_args.pop("page", None)
    base_args["per_page"] = per_page
    view_args = dict(request.view_args or {})
    for key in view_args:
        base_args.pop(key, None)

    def page_url(target_page: int) -> str:
        values = dict(view_args)
        values.update(base_args)
        values["page"] = target_page
        return url_for(request.endpoint, **values)

    return {
        "page": page,
        "per_page": per_page,
        "total_count": total_count,
        "total_pages": total_pages,
        "previous_url": page_url(page - 1) if page > 1 else None,
        "next_url": page_url(page + 1) if page < total_pages else None,
        "per_page_options": LEDGER_PER_PAGE_OPTIONS,
    }


def _ledger_export_url(project_id: int | None, filters: dict) -> str:
    values = {
        key: value
        for key, value in filters.items()
        if value not in (None, "")
    }
    if project_id is not None:
        values["project_id"] = project_id
    return url_for("web.download_export", export_type="project-ledger", **values)


def _delete_upload_file(filename: str | None) -> None:
    from pathlib import Path
    from flask import current_app

    if not filename:
        return
    root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    target = (root / str(filename)).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return
    if target.is_file():
        target.unlink()


def _save_form_upload(field_name: str, *, purpose: str = "document") -> str:
    from pathlib import Path
    from flask import current_app
    from construction_maintenance.services.imports import save_upload

    file = request.files.get(field_name)
    if not file or not file.filename:
        return ""

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    stored = save_upload(upload_folder, file, purpose=purpose)
    return stored.name


@bp.app_template_filter("money")
def money(value: float) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


@bp.app_template_filter("money_short")
def money_short(value: float) -> str:
    try:
        val = float(value)
        if val >= 10000 or val <= -10000:
            return f"{val / 10000:,.2f}万"
        return f"{val:,.2f}"
    except (TypeError, ValueError):
        return "0.00"


@bp.app_template_filter("upload_name")
def upload_name(value: str) -> str:
    return str(value or "").replace("\\", "/").rstrip("/").split("/")[-1]


@bp.app_template_filter("fromjson")
def fromjson_filter(value: str) -> dict:
    import json
    try:
        return json.loads(value or "{}")
    except Exception:
        return {}


@bp.route("/login", methods=["GET", "POST"])
def login():
    next_target = request.args.get("next")
    if request.method == "POST":
        username = request.form.get("username", "")
        raw_key = f"{username.strip().casefold()}|{request.remote_addr or ''}"
        attempt_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        now = int(time.time())
        if repo.login_attempt_is_locked(attempt_key, now):
            return render_template("login.html", next=next_target), 429

        user = authenticate_user(username, request.form.get("password", ""))
        if user:
            repo.clear_login_failures(attempt_key)
            login_user(user)
            if user["must_change_password"]:
                return redirect(url_for("web.settings", tab="security"))
            return redirect(safe_redirect_target(next_target, url_for("web.dashboard")))
        locked = repo.record_login_failure(attempt_key, now)
        status = 429 if locked else 401
        return render_template("login.html", next=next_target), status

    return render_template("login.html", next=next_target)


@bp.post("/logout")
def logout():
    logout_user()
    return redirect(url_for("web.login"))


@bp.get("/settings")
@require_admin
def settings():
    requested_tab = request.args.get("tab", "security")
    allowed_tabs = {"security"}
    if g.admin_user["role"] == "super_admin":
        allowed_tabs.update({"admins", "general", "audit"})
    active_tab = requested_tab if requested_tab in allowed_tabs else "security"
    return render_template(
        "settings.html",
        active_tab=active_tab,
        admin_users=(
            repo.list_admin_users()
            if g.admin_user["role"] == "super_admin"
            else []
        ),
        audit_events=(
            repo.list_audit_events()
            if g.admin_user["role"] == "super_admin" and active_tab == "audit"
            else []
        ),
    )


@bp.post("/settings/password")
@require_admin
def change_password():
    new_password = request.form.get("new_password", "")
    if new_password != request.form.get("confirm_password", ""):
        flash("两次输入的新密码不一致", "danger")
        return redirect(url_for("web.settings", tab="security"))
    try:
        repo.change_own_password(
            g.admin_user["id"],
            request.form.get("current_password", ""),
            new_password,
        )
        flash("登录密码已更新，请妥善保管新密码", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("web.settings", tab="security"))


@bp.post("/settings/admins")
@require_super_admin
def create_admin():
    password = request.form.get("password", "")
    if password != request.form.get("confirm_password", ""):
        flash("两次输入的初始密码不一致", "danger")
        return redirect(url_for("web.settings", tab="admins"))
    try:
        repo.create_admin_user(
            {
                "username": request.form.get("username"),
                "display_name": request.form.get("display_name"),
                "password": password,
                "role": request.form.get("role", "admin"),
                "is_active": request.form.get("is_active") == "1",
            }
        )
        flash("管理员账号已创建，首次登录时须修改密码", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("web.settings", tab="admins"))


@bp.post("/settings/admins/<int:user_id>/update")
@require_super_admin
def update_admin(user_id: int):
    try:
        repo.update_admin_user(
            user_id,
            {
                "display_name": request.form.get("display_name"),
                "role": request.form.get("role"),
                "is_active": request.form.get("is_active") == "1",
            },
            actor_id=g.admin_user["id"],
        )
        flash("管理员账号设置已保存", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("web.settings", tab="admins"))


@bp.post("/settings/admins/<int:user_id>/reset-password")
@require_super_admin
def reset_admin_password(user_id: int):
    password = request.form.get("password", "")
    if password != request.form.get("confirm_password", ""):
        flash("两次输入的新密码不一致", "danger")
        return redirect(url_for("web.settings", tab="admins"))
    try:
        repo.reset_admin_password(user_id, password)
        flash("密码已重置，该账号下次登录时须修改密码", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("web.settings", tab="admins"))


@bp.post("/settings/general")
@require_super_admin
def update_general_settings():
    system_name = request.form.get("system_name", "").strip()
    organization_name = request.form.get("organization_name", "").strip()
    support_contact = request.form.get("support_contact", "").strip()
    try:
        timeout_minutes = int(request.form.get("session_timeout_minutes", ""))
        if not 15 <= timeout_minutes <= 1440:
            raise ValueError
    except ValueError:
        flash("会话超时时间须为 15 至 1440 分钟", "danger")
        return redirect(url_for("web.settings", tab="general"))

    if not system_name:
        flash("系统名称不能为空", "danger")
    elif len(system_name) > 80:
        flash("系统名称不能超过 80 个字符", "danger")
    elif len(organization_name) > 100:
        flash("组织名称不能超过 100 个字符", "danger")
    elif len(support_contact) > 100:
        flash("支持联系方式不能超过 100 个字符", "danger")
    else:
        repo.update_system_settings(
            {
                "system_name": system_name,
                "organization_name": organization_name,
                "support_contact": support_contact,
                "session_timeout_minutes": str(timeout_minutes),
            }
        )
        flash("系统基本设置已保存", "success")
    return redirect(url_for("web.settings", tab="general"))


def _download_name_for_upload(filename: str) -> str:
    name = upload_name(filename)
    if "." in name:
        return name

    legacy_suffixes = {
        "_pdf": ".pdf",
        "_jpg": ".jpg",
        "_jpeg": ".jpeg",
        "_png": ".png",
    }
    lower_name = name.lower()
    for marker, extension in legacy_suffixes.items():
        if lower_name.endswith(marker):
            return f"{name[:-len(marker)]}{extension}"
    return name


@bp.get("/")
def dashboard():
    from construction_maintenance.services.dashboard import build_dashboard
    return render_template("dashboard.html", metrics=build_dashboard())


@bp.route("/expense-categories", methods=["GET", "POST"])
def expense_categories():
    if request.method == "POST":
        has_parent_id = "parent_id" in request.form
        parent_id = (
            optional_int(request.form, "parent_id", "所属分类编号")
            if has_parent_id
            else None
        )
        try:
            category_data = {
                "name": required_text(request.form, "name", "费用科目名称"),
                "transaction_scope": text_value(request.form, "transaction_scope") or "支出",
                "sort_order": text_value(request.form, "sort_order"),
            }
            if has_parent_id:
                category_data["parent_id"] = parent_id
            repo.create_expense_category(category_data)
            flash("费用科目已成功添加。", "success")
        except (sqlite3.IntegrityError, ValueError) as exc:
            flash(str(exc) or "添加失败：该科目名称已存在。", "danger")
        redirect_url = request.form.get("redirect")
        return redirect(
            safe_redirect_target(redirect_url, url_for("web.expense_categories"))
        )

    categories = repo.list_expense_categories(include_inactive=True)
    return render_template(
        "expense_categories.html",
        categories=categories,
        roots=[row for row in categories if row["parent_id"] is None],
        leaves=[row for row in categories if row["parent_id"] is not None],
    )


@bp.route("/expense-categories/<int:category_id>/edit", methods=["POST"])
def edit_expense_category(category_id: int):
    has_parent_id = "parent_id" in request.form
    parent_id = (
        optional_int(request.form, "parent_id", "所属分类编号")
        if has_parent_id
        else None
    )
    try:
        category_data = {
            "name": required_text(request.form, "name", "费用科目名称"),
            "sort_order": text_value(request.form, "sort_order"),
            "is_active": 1 if request.form.get("is_active") else 0,
        }
        if has_parent_id:
            category_data["parent_id"] = parent_id
        if "transaction_scope" in request.form:
            category_data["transaction_scope"] = text_value(
                request.form, "transaction_scope"
            )
        repo.update_expense_category(category_id, category_data)
        flash("费用科目已成功修改。", "success")
    except (sqlite3.IntegrityError, ValueError) as exc:
        flash(str(exc) or "修改失败：该科目名称已存在。", "danger")
    redirect_url = request.form.get("redirect")
    return redirect(
        safe_redirect_target(redirect_url, url_for("web.expense_categories"))
    )


@bp.post("/expense-categories/<int:category_id>/migrate")
def migrate_expense_category(category_id: int):
    target_id = int(required_text(request.form, "target_id", "目标分类"))
    repo.migrate_expense_category(
        category_id, target_id, actor_admin_id=_actor_id()
    )
    flash("分类引用已迁移，原分类已停用。", "success")
    return redirect(url_for("web.expense_categories"))


@bp.post("/expense-categories/<int:category_id>/delete")
def delete_expense_category(category_id: int):
    try:
        repo.delete_expense_category(category_id)
        flash("费用科目已成功删除。", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("web.expense_categories"))



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


@bp.route("/projects/<int:project_id>/edit", methods=["POST"])
def edit_project(project_id: int):
    repo.update_project(
        project_id,
        {
            "name": required_text(request.form, "name", "项目名称"),
            "status": text_value(request.form, "status") or "进行中",
            "owner": text_value(request.form, "owner"),
            "start_date": text_value(request.form, "start_date"),
            "end_date": text_value(request.form, "end_date"),
            "notes": text_value(request.form, "notes"),
        }
    )
    return redirect(url_for("web.projects"))


@bp.route("/projects/<int:project_id>/delete", methods=["POST"])
def delete_project(project_id: int):
    try:
        repo.delete_project(project_id, actor_admin_id=_actor_id())
        flash("工程项目已成功删除。", "success")
    except ValueError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("web.projects"))


@bp.route("/vouchers", methods=["GET", "POST"])
def vouchers():
    if request.method == "POST":
        payload = {
            "project_id": int(required_text(request.form, "project_id", "项目")),
            "voucher_date": required_text(request.form, "voucher_date", "日期"),
            "transaction_type": required_text(
                request.form, "transaction_type", "收支类型"
            ),
            "category_id": int(
                required_text(request.form, "category_id", "二级分类")
            ),
            "amount": required_text(request.form, "amount", "金额"),
            "notes": text_value(request.form, "notes"),
            "handler_name": text_value(request.form, "handler_name"),
            "payment_status": required_text(
                request.form, "payment_status", "付款状态"
            ),
            "payment_date": text_value(request.form, "payment_date"),
            "payment_notes": text_value(request.form, "payment_notes"),
            "review_status": text_value(request.form, "review_status") or "已确认",
            "actor_admin_id": _actor_id(),
        }
        repo.create_voucher(payload)
        return redirect(
            safe_redirect_target(request.referrer, url_for("web.vouchers"))
        )

    filter_project_id = request.args.get("project_id", type=int)
    filters = _ledger_filters()
    requested_page, per_page = _ledger_pagination_params()
    total_count = repo.count_vouchers(
        project_id=filter_project_id,
        include_voided=True,
        **filters,
    )
    pagination = _ledger_pagination_context(
        total_count, requested_page, per_page
    )
    vouchers_list = repo.list_vouchers(
        project_id=filter_project_id,
        include_voided=True,
        limit=per_page,
        offset=(pagination["page"] - 1) * per_page,
        **filters,
    )
    categories = repo.list_expense_categories(include_inactive=False)

    return render_template(
        "vouchers.html",
        projects=repo.list_projects(),
        vouchers=vouchers_list,
        voucher_total_count=total_count,
        pagination=pagination,
        filter_project_id=filter_project_id,
        financial_summary=repo.get_project_financial_summary(
            filter_project_id, **filters
        ),
        ledger_export_url=_ledger_export_url(filter_project_id, filters),
        ledger_filters=filters,
        voucher_types=repo.list_expense_category_names(),
        batch_items=repo.list_batch_items(item_type="voucher"),
        categories=categories,
        category_json=[dict(row) for row in categories],
        transaction_types=TRANSACTION_TYPES,
        payment_statuses=PAYMENT_STATUSES,
        review_statuses=REVIEW_STATUSES,
    )


@bp.route("/projects/<int:project_id>/vouchers")
def project_vouchers(project_id: int):
    # 查找特定项目的基本信息
    project = next((p for p in repo.list_projects() if int(p["id"]) == project_id), None)
    if not project:
        return "Project not found", 404
        
    filters = _ledger_filters()
    requested_page, per_page = _ledger_pagination_params()
    total_count = repo.count_vouchers(
        project_id=project_id,
        include_voided=True,
        **filters,
    )
    pagination = _ledger_pagination_context(
        total_count, requested_page, per_page
    )
    vouchers_list = repo.list_vouchers(
        project_id=project_id,
        include_voided=True,
        limit=per_page,
        offset=(pagination["page"] - 1) * per_page,
        **filters,
    )
    summary = repo.get_project_financial_summary(project_id, **filters)
    categories = repo.list_expense_categories(include_inactive=False)
    
    return render_template(
        "project_vouchers.html",
        project=project,
        projects=repo.list_projects(),
        vouchers=vouchers_list,
        voucher_total_count=total_count,
        pagination=pagination,
        total_spending=summary["net_expense"],
        active_voucher_count=summary["entry_count"],
        financial_summary=summary,
        ledger_export_url=_ledger_export_url(project_id, filters),
        ledger_filters=filters,
        voucher_types=repo.list_expense_category_names(),
        filter_voucher_types=_voucher_type_choices(project_id),
        batch_items=repo.list_batch_items(item_type="voucher"),
        categories=categories,
        category_json=[dict(row) for row in categories],
        transaction_types=TRANSACTION_TYPES,
        payment_statuses=PAYMENT_STATUSES,
        review_statuses=REVIEW_STATUSES,
    )


@bp.get("/ledger-pending")
def ledger_pending():
    project_id = request.args.get("project_id", type=int)
    status = request.args.get("status", "待补录").strip()
    if status not in PENDING_STATUSES:
        raise ValueError("待补录状态无效")
    requested_page, per_page = _ledger_pagination_params(default_per_page=15)
    total_count = repo.count_ledger_pending_items(
        project_id=project_id,
        status=status,
    )
    pagination = _ledger_pagination_context(
        total_count, requested_page, per_page
    )
    categories = repo.list_expense_categories(include_inactive=False)
    return render_template(
        "ledger_pending.html",
        items=repo.list_ledger_pending_items(
            project_id=project_id,
            status=status,
            limit=per_page,
            offset=(pagination["page"] - 1) * per_page,
        ),
        pending_total_count=total_count,
        pagination=pagination,
        projects=repo.list_projects(),
        categories=categories,
        category_json=[dict(row) for row in categories],
        filter_project_id=project_id,
        filter_status=status,
        pending_statuses=PENDING_STATUSES,
        transaction_types=TRANSACTION_TYPES,
        payment_statuses=PAYMENT_STATUSES,
    )


@bp.post("/ledger-pending/<int:item_id>/complete")
def complete_ledger_pending(item_id: int):
    repo.convert_ledger_pending_item(
        item_id,
        amount=required_text(request.form, "amount", "金额"),
        category_id=int(required_text(request.form, "category_id", "二级分类")),
        transaction_type=required_text(request.form, "transaction_type", "收支类型"),
        payment_status=required_text(request.form, "payment_status", "付款状态"),
        actor_admin_id=_actor_id(),
    )
    flash("待补录事项已转正式明细。", "success")
    return redirect(url_for("web.ledger_pending", status="已转正式明细"))


@bp.post("/ledger-pending/<int:item_id>/ignore")
def ignore_ledger_pending(item_id: int):
    repo.ignore_ledger_pending_item(item_id, actor_admin_id=_actor_id())
    flash("待补录事项已忽略。", "success")
    return redirect(url_for("web.ledger_pending", status="待补录"))


def _render_people_and_attendance(active_tab):
    import datetime
    import calendar

    # --- 1. 花名册基础数据 ---
    all_people = repo.list_people()
    is_attendance_view = active_tab == "attendance"
    people_query = request.args.get("q", "").strip()
    filtered_people = all_people
    if people_query and not is_attendance_view:
        needle = people_query.casefold()
        filtered_people = [
            person
            for person in all_people
            if needle
            in " ".join(
                str(person[field] or "")
                for field in ("name", "id_number", "phone", "job_type")
            ).casefold()
        ]
    people_page_size = 15
    people_total_pages = max(
        1, (len(filtered_people) + people_page_size - 1) // people_page_size
    )
    requested_page = request.args.get("page", 1, type=int) or 1
    people_page = max(1, min(requested_page, people_total_pages))
    start = (people_page - 1) * people_page_size
    visible_people = (
        [] if is_attendance_view else filtered_people[start : start + people_page_size]
    )
    batch_items = [] if is_attendance_view else repo.list_batch_items(item_type="person")

    # --- 2. 考勤数据计算 ---
    now = datetime.datetime.now()
    current_month_str = now.strftime("%Y-%m")
    month = request.args.get("month", current_month_str)

    try:
        month, year, month_num = _parse_month(month)
    except ValueError:
        month = current_month_str
        month, year, month_num = _parse_month(month)

    _, total_days = calendar.monthrange(year, month_num)

    days = []
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    for d in range(1, total_days + 1):
        dt = datetime.date(year, month_num, d)
        day_str = f"{d:02d}"
        weekday = weekdays[dt.weekday()]
        days.append({
            "day": d,
            "day_str": day_str,
            "date_str": f"{month}-{day_str}",
            "weekday": weekday,
            "is_weekend": dt.weekday() in (5, 6),
        })

    attendance_people = repo.list_attendance_people() if is_attendance_view else []
    raw_attendance = repo.list_attendance_by_month(month) if is_attendance_view else []

    attendance_dict = {}
    for record in raw_attendance:
        p_id = record["person_id"]
        date_str = record["work_date"]
        shift = record["shift_type"]
        if p_id not in attendance_dict:
            attendance_dict[p_id] = {}
        attendance_dict[p_id][date_str] = shift

    person_stats = {}
    for p in attendance_people:
        p_id = p["id"]
        p_att = attendance_dict.get(p_id, {})
        p_day = sum(1 for s in p_att.values() if s in ("白班", "夜班", "上班"))
        p_leave = sum(1 for s in p_att.values() if s == "请假")
        person_stats[p_id] = {
            "day": p_day,
            "night": 0,
            "leave": p_leave,
            "total": p_day,
        }

    total_shifts = sum(1 for r in raw_attendance if r["shift_type"] in ("白班", "夜班", "上班"))
    day_shifts = total_shifts
    night_shifts = 0
    leave_shifts = sum(1 for r in raw_attendance if r["shift_type"] == "请假")

    salary_summary = repo.get_salary_summary_by_month(month) if is_attendance_view else []
    salary_payments = repo.list_salary_payments(month=month) if is_attendance_view else []

    from construction_maintenance.services import contract_generator as cg
    projects = repo.list_projects()
    contract_templates = cg.list_contract_templates()

    all_contracts = repo.list_contracts()
    person_contracts = {}
    for c in all_contracts:
        row_dict = dict(c)
        if row_dict.get("person_id"):
            p_id = row_dict["person_id"]
            if p_id not in person_contracts:
                person_contracts[p_id] = row_dict

    return render_template(
        "people.html",
        active_tab=active_tab,
        people=visible_people,
        people_query=people_query,
        people_page=people_page,
        people_total_pages=people_total_pages,
        people_total_count=len(filtered_people),
        batch_items=batch_items,
        attendance_people=attendance_people,
        all_people=all_people,
        days=days,
        month=month,
        attendance_dict=attendance_dict,
        person_stats=person_stats,
        salary_summary=salary_summary,
        salary_payments=salary_payments,
        projects=projects,
        contract_templates=contract_templates,
        person_contracts=person_contracts,
        metrics={
            "total_people": len(attendance_people),
            "total_shifts": total_shifts,
            "day_shifts": day_shifts,
            "night_shifts": night_shifts,
            "leave_shifts": leave_shifts,
        },
    )


@bp.route("/people", methods=["GET", "POST"])
def people():
    if request.method == "POST":
        attachment_path = ""
        try:
            attachment_path = _save_form_upload("id_card_attachment")
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
                    "id_card_path": attachment_path,
                    "is_attendance": 1 if request.form.get("is_attendance") else 0,
                    "salary_type": text_value(request.form, "salary_type") or "日薪",
                    "salary_rate": float(text_value(request.form, "salary_rate") or 0.0),
                }
            )
            flash("人员档案已成功录入。", "success")
        except sqlite3.IntegrityError:
            _delete_upload_file(attachment_path)
            flash("录入失败：该身份证号已被登记。", "danger")
        except Exception:
            _delete_upload_file(attachment_path)
            raise
        return redirect(url_for("web.people"))
    
    active_tab = request.args.get("tab", "people")
    return _render_people_and_attendance(active_tab)


@bp.route("/attendance", methods=["GET"])
def attendance():
    return _render_people_and_attendance("attendance")


@bp.route("/attendance/salary-payments/add", methods=["POST"])
def add_salary_payment():
    from construction_maintenance.web.routes import required_text, text_value
    try:
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict()
        data["actor_admin_id"] = _actor_id()
            
        if not data.get("person_id") or not data.get("payment_date") or not data.get("payment_type") or not data.get("amount"):
            if request.is_json:
                return {"status": "error", "message": "缺失必要参数"}, 400
            flash("登记失败：缺失必要参数", "error")
            return redirect(url_for("web.people", tab="attendance"))
            
        repo.create_salary_payment(data)
        
        if request.is_json:
            return {"status": "success"}
        flash("预支/发薪流水登记成功！", "success")
        return redirect(url_for("web.people", tab="attendance", month=data.get("payment_date")[:7]))
    except (TypeError, ValueError, sqlite3.IntegrityError) as exc:
        if request.is_json:
            return {"status": "error", "message": str(exc)}, 400
        flash(f"登记失败：{str(exc)}", "error")
        return redirect(url_for("web.people", tab="attendance"))


@bp.route("/attendance/salary-payments/<int:payment_id>/delete", methods=["POST"])
def delete_salary_payment(payment_id):
    try:
        payments = repo.list_salary_payments()
        target_payment = next((p for p in payments if p["id"] == payment_id), None)
        redirect_month = None
        if target_payment:
            redirect_month = target_payment["payment_date"][:7]
            
        repo.delete_salary_payment(payment_id)
        repo.record_audit(
            "delete",
            "salary_payment",
            payment_id,
            actor_admin_id=_actor_id(),
            details={
                "person_id": target_payment["person_id"] if target_payment else None,
                "amount": target_payment["amount"] if target_payment else None,
            },
        )
        
        if request.is_json:
            return {"status": "success"}
        flash("流水删除成功！", "success")
        
        if redirect_month:
            return redirect(url_for("web.people", tab="attendance", month=redirect_month))
        return redirect(url_for("web.people", tab="attendance"))
    except Exception as exc:
        if request.is_json:
            return {"status": "error", "message": str(exc)}, 500
        flash(f"删除失败：{str(exc)}", "error")
        return redirect(url_for("web.people", tab="attendance"))



@bp.post("/attendance/update")
def update_attendance():
    data = request.get_json() or {}
    person_id = data.get("person_id")
    date = data.get("date")
    shift_type = data.get("shift_type")

    if not person_id or not date:
        return {"status": "error", "message": "缺失必要参数"}, 400

    try:
        person_id = int(person_id)
        work_date = _parse_iso_date(date, "考勤日期")
        if shift_type not in (None, "", "上班", "请假", "白班", "夜班"):
            raise ValueError("考勤状态无效")
        if shift_type in ("白班", "夜班"):
            shift_type = "上班"
        repo.save_attendance(person_id, work_date, shift_type)
    except (TypeError, ValueError, sqlite3.IntegrityError) as exc:
        return {"status": "error", "message": str(exc)}, 400
    return {"status": "success"}


@bp.post("/attendance/settings/update")
def update_attendance_settings():
    data = request.get_json() or {}
    is_attendance_map = data.get("is_attendance_map", {})
    if not isinstance(is_attendance_map, dict):
        return {"status": "error", "message": "考勤名单参数无效"}, 400
    status_map = {}
    for p_id_str, is_att in is_attendance_map.items():
        try:
            person_id = int(p_id_str)
            status = int(is_att)
            if status not in (0, 1):
                raise ValueError
            status_map[person_id] = status
        except (ValueError, TypeError):
            return {"status": "error", "message": "考勤名单参数无效"}, 400
    try:
        repo.update_people_attendance_status(status_map)
        return {"status": "success"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}, 500


@bp.post("/attendance/batch-fill")
def batch_fill_attendance():
    data = request.get_json() or {}
    month = data.get("month")
    shift_type = data.get("shift_type", "上班")
    
    if not month:
        return {"status": "error", "message": "缺失必要参数"}, 400
        
    try:
        # 获取所有当前参与考勤的人员
        people = repo.list_attendance_people()
        
        # 计算当月的所有日期
        month, year, m = _parse_month(month)
        if shift_type not in ("上班", "请假"):
            raise ValueError("考勤状态无效")
        _, num_days = calendar.monthrange(year, m)
        
        db = repo.get_db()
        # 批量填报考勤
        for p in people:
            for d in range(1, num_days + 1):
                date_str = f"{month}-{d:02d}"
                # 排除周末：不填报周六和周日，保持默认休息状态，非常人性化
                import datetime
                dt = datetime.date(year, m, d)
                if dt.weekday() in [5, 6]:
                    continue
                
                db.execute(
                    """
                    insert into attendance (person_id, work_date, shift_type)
                    values (?, ?, ?)
                    on conflict(person_id, work_date) do update set shift_type = excluded.shift_type
                    """,
                    (p["id"], date_str, shift_type),
                )
        db.commit()
        return {"status": "success"}
    except (TypeError, ValueError, sqlite3.IntegrityError) as exc:
        return {"status": "error", "message": str(exc)}, 400


@bp.route("/attendance/salary-payments/quota", methods=["GET"])
def get_salary_quota():
    person_id_str = request.args.get("person_id")
    month = request.args.get("month")
    
    if not person_id_str or not month:
        return {"status": "error", "message": "缺失必要参数"}, 400
        
    try:
        pid = int(person_id_str)
        month, _, _ = _parse_month(month)
        summary = repo.get_salary_summary_by_month(month)
        for item in summary:
            if item["person_id"] == pid:
                return {
                    "status": "success",
                    "earnings": item["earnings"],
                    "advance": item["advance"],
                    "payout": item["payout"],
                    "balance": item["balance"]
                }
        return {
            "status": "success",
            "earnings": 0.0,
            "advance": 0.0,
            "payout": 0.0,
            "balance": 0.0
        }
    except (TypeError, ValueError) as exc:
        return {"status": "error", "message": str(exc)}, 400


@bp.route("/attendance/export", methods=["GET"])
def export_attendance():
    from io import BytesIO
    from construction_maintenance.services.exports import build_attendance_workbook

    month = request.args.get("month", "")
    is_template = request.args.get("template") == "1"

    if not month:
        import datetime
        month = datetime.datetime.now().strftime("%Y-%m")

    try:
        month, _, _ = _parse_month(month)
    except ValueError as exc:
        return str(exc), 400

    try:
        workbook = build_attendance_workbook(month, is_template)
        out = BytesIO()
        workbook.save(out)
        out.seek(0)

        filename = f"{month}_考勤模板.xlsx" if is_template else f"{month}_月度考勤表.xlsx"
        return send_file(
            out,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        flash(f"导出失败: {str(exc)}")
        return redirect(url_for("web.people", tab="attendance", month=month))


@bp.post("/attendance/import")
def import_attendance():
    from pathlib import Path
    import os
    from flask import current_app
    from construction_maintenance.services.imports import save_upload, import_attendance_workbook

    month = request.form.get("month")
    file = request.files.get("file")
    if not file or not month:
        return {"status": "error", "message": "缺少上传的文件或月份参数"}, 400

    try:
        month, _, _ = _parse_month(month)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}, 400

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    temp_path = None
    try:
        temp_path = save_upload(upload_folder, file, purpose="spreadsheet")
        res = import_attendance_workbook(temp_path, month)
        return res
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}, 400
    except Exception as exc:
        return {"status": "error", "message": f"服务器内部错误: {str(exc)}"}, 500
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@bp.route("/qualifications", methods=["GET", "POST"])
def qualifications():
    if request.method == "POST":
        if text_value(request.form, "company_name"):
            company_id = repo.create_company(
                {
                    "name": required_text(request.form, "company_name", "公司名称"),
                    "credit_code": text_value(request.form, "credit_code"),
                    "legal_person": text_value(request.form, "legal_person"),
                    "phone": text_value(request.form, "phone"),
                    "notes": text_value(request.form, "company_notes"),
                    "is_main": 0,
                }
            )
        else:
            company_id = int(required_text(request.form, "company_id", "公司"))
        from pathlib import Path
        from flask import current_app
        from construction_maintenance.services.imports import save_upload

        attachment_path = ""
        file = request.files.get("attachment")
        if file and file.filename:
            upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
            stored = save_upload(upload_folder, file)
            attachment_path = stored.name

        try:
            repo.create_qualification(
                {
                    "company_id": company_id,
                    "name": required_text(request.form, "name", "资质名称"),
                    "certificate_no": required_text(
                        request.form, "certificate_no", "证书编号"
                    ),
                    "issue_date": text_value(request.form, "issue_date"),
                    "expiry_date": text_value(request.form, "expiry_date"),
                    "is_long_term": 1 if request.form.get("is_long_term") else 0,
                    "attachment_path": attachment_path,
                    "notes": text_value(request.form, "notes"),
                }
            )
        except Exception:
            _delete_upload_file(attachment_path)
            raise
        return redirect(url_for("web.qualifications"))
    return render_template(
        "qualifications.html",
        companies=repo.list_companies(),
        qualifications=repo.list_qualifications(),
    )


@bp.route("/batch", methods=["GET", "POST"])
def batch():
    from pathlib import Path
    from flask import current_app
    from construction_maintenance.services.imports import save_upload
    import json

    if request.method == "POST":
        item_type = text_value(request.form, "item_type") or "voucher"
        if item_type not in {"voucher", "person", "qualification"}:
            raise ValueError("批量导入类型无效")
        upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
        app = current_app._get_current_object()
        
        for file in request.files.getlist("files"):
            if not file.filename:
                continue
            stored = save_upload(upload_folder, file)
            
            if current_app.config.get("TESTING"):
                try:
                    ocr_result = recognize_batch_upload(stored, item_type)
                    status = ocr_result.status
                    recognized_json = json.dumps(ocr_result.data, ensure_ascii=False)
                    confidence = ocr_result.confidence
                except Exception as exc:
                    status = "待确认"
                    recognized_json = json.dumps(
                        {"message": f"OCR 识别失败，请人工确认：{exc}"},
                        ensure_ascii=False,
                    )
                    confidence = None

                repo.create_batch_item(
                    {
                        "item_type": item_type,
                        "source_filename": file.filename,
                        "stored_path": stored.name,
                        "status": status,
                        "recognized_json": recognized_json,
                        "confidence": confidence,
                    }
                )
            else:
                # 生产与开发模式下，进行异步多线程处理
                item_id = repo.create_batch_item(
                    {
                        "item_type": item_type,
                        "source_filename": file.filename,
                        "stored_path": stored.name,
                        "status": "识别中",
                        "recognized_json": json.dumps({"message": "正在进行 AI 智能识别..."}, ensure_ascii=False),
                        "confidence": None,
                    }
                )
                ocr_executor.submit(
                    _async_ocr_worker,
                    app,
                    item_id,
                    str(stored),
                    item_type
                )
        return redirect(url_for("web.batch"))
    return render_template(
        "batch.html",
        items=repo.list_batch_items(),
        projects=repo.list_projects(),
        categories=repo.list_expense_category_names(),
        companies=repo.list_companies(),
    )


def _get_batch_item_summary(item):
    import json
    try:
        parsed = json.loads(item["recognized_json"])
    except Exception:
        return item["recognized_json"] or ""

    parts = []
    if item["item_type"] == "voucher":
        if parsed.get("voucher_date"):
            parts.append(f"日期: {parsed['voucher_date']}")
        if parsed.get("amount"):
            parts.append(f"金额: ¥{parsed['amount']}")
        if parsed.get("payment_method"):
            parts.append(f"方式: {parsed['payment_method']}")
        if parsed.get("notes"):
            parts.append(f"备注: {parsed['notes']}")
    elif item["item_type"] == "qualification":
        if parsed.get("company_name"):
            parts.append(f"公司: {parsed['company_name']}")
        if parsed.get("name_select"):
            parts.append(f"名称: {parsed['name_select']}")
        if parsed.get("certificate_no"):
            parts.append(f"编号: {parsed['certificate_no']}")
        if parsed.get("notes"):
            parts.append(f"备注: {parsed['notes']}")
    else:  # person
        if parsed.get("name"):
            parts.append(f"姓名: {parsed['name']}")
        if parsed.get("id_number"):
            parts.append(f"号码: {parsed['id_number']}")
        if parsed.get("notes"):
            parts.append(f"备注: {parsed['notes']}")

    return " | ".join(parts) if parts else item["recognized_json"] or ""


@bp.route("/batch/item/<int:item_id>/render")
def render_batch_item(item_id: int):
    item = repo.get_batch_item(item_id)
    if not item:
        return {"error": "Item not found"}, 404

    html = render_template(
        "_batch_card.html",
        item=item,
        projects=repo.list_projects(),
        categories=repo.list_expense_category_names(),
        companies=repo.list_companies(),
    )

    conf_val = ""
    if item["confidence"] is not None:
        conf_val = f"{int(item['confidence'] * 100)}%"

    return {
        "id": item["id"],
        "status": item["status"],
        "confidence": conf_val,
        "summary": _get_batch_item_summary(item),
        "html": html
    }


@bp.post("/batch/<int:item_id>/confirm")
def confirm_batch_item(item_id: int):
    item = repo.get_batch_item(item_id)
    if not item:
        flash("批量条目不存在", "danger")
        return redirect(url_for("web.batch"))

    if item["item_type"] == "voucher":
        project_id_str = request.form.get("project_id")
        voucher_date = request.form.get("voucher_date")
        voucher_type = request.form.get("voucher_type")
        amount_str = request.form.get("amount")
        notes = request.form.get("notes") or ""
        entry_user = request.form.get("entry_user") or "AI确认导入"

        if not project_id_str:
            flash("请选择归属项目", "danger")
            return redirect(url_for("web.batch"))
        try:
            project_id = int(project_id_str)
        except ValueError:
            flash("无效的项目ID", "danger")
            return redirect(url_for("web.batch"))

        if not voucher_date:
            flash("请选择凭证日期", "danger")
            return redirect(url_for("web.batch"))

        if not amount_str:
            flash("请填写凭证金额", "danger")
            return redirect(url_for("web.batch"))

        try:
            from construction_maintenance.repositories import normalize_amount
            amount = normalize_amount(amount_str)
        except Exception as exc:
            flash(f"凭证金额无效: {exc}", "danger")
            return redirect(url_for("web.batch"))

        attachment_path = item["stored_path"] or ""

        try:
            repo.create_voucher({
                "project_id": project_id,
                "voucher_date": voucher_date,
                "voucher_type": voucher_type or "其它",
                "amount": amount,
                "notes": notes,
                "attachment_path": attachment_path,
                "entry_user": entry_user,
                "actor_admin_id": _actor_id(),
            })
            repo.update_batch_item_status(item_id, "已确认")
            flash("凭证成功导入项目台账！", "success")
        except Exception as exc:
            flash(f"导入失败: {exc}", "danger")

    elif item["item_type"] == "person":
        name = request.form.get("name")
        id_number = request.form.get("id_number")
        gender = request.form.get("gender") or ""
        birth_date = request.form.get("birth_date") or ""
        address = request.form.get("address") or ""
        notes = request.form.get("notes") or ""
        phone = request.form.get("phone") or ""
        job_type = request.form.get("job_type") or ""

        if not name or not id_number:
            flash("姓名与身份证号为必填项", "danger")
            return redirect(url_for("web.batch"))

        try:
            repo.create_person({
                "name": name,
                "id_number": id_number,
                "gender": gender,
                "birth_date": birth_date,
                "address": address,
                "notes": notes,
                "phone": phone,
                "job_type": job_type,
                "id_card_path": item["stored_path"] or "",
                "review_status": "已确认"
            })
            repo.update_batch_item_status(item_id, "colleague_approved" if False else "已确认")
            flash("人员信息成功导入花名册！", "success")
        except Exception as exc:
            flash(f"导入失败: {exc}", "danger")

    elif item["item_type"] == "qualification":
        company_id_str = request.form.get("company_id")
        company_name = request.form.get("company_name") or ""
        name_select = request.form.get("name_select")
        name_custom = request.form.get("name_custom") or ""
        certificate_no = request.form.get("certificate_no")
        issue_date = request.form.get("issue_date") or ""
        expiry_date = request.form.get("expiry_date") or ""
        is_long_term = int(request.form.get("is_long_term") or 0)
        credit_code = request.form.get("credit_code") or ""
        legal_person = request.form.get("legal_person") or ""
        phone = request.form.get("phone") or ""
        notes = request.form.get("notes") or ""

        company_id = None
        if company_id_str:
            try:
                company_id = int(company_id_str)
            except ValueError:
                pass

        if not company_id:
            if company_name:
                try:
                    company_id = repo.create_company({
                        "name": company_name,
                        "credit_code": credit_code,
                        "legal_person": legal_person,
                        "phone": phone,
                        "notes": "由企业资质批量录入自动创建"
                    })
                except Exception as exc:
                    flash(f"自动创建合作公司失败: {exc}", "danger")
                    return redirect(url_for("web.batch"))
            else:
                flash("请选择已有的关联合作公司，或填写新增合作单位名称", "danger")
                return redirect(url_for("web.batch"))

        cert_name = name_select
        if not cert_name or cert_name == "CUSTOM":
            cert_name = name_custom
        cert_name = (cert_name or "").strip()
        if not cert_name:
            flash("资质证书/证照名称不能为空", "danger")
            return redirect(url_for("web.batch"))

        attachment_path = item["stored_path"] or ""

        try:
            repo.create_qualification({
                "company_id": company_id,
                "name": cert_name,
                "certificate_no": certificate_no or "",
                "issue_date": issue_date,
                "expiry_date": "" if is_long_term else expiry_date,
                "is_long_term": is_long_term,
                "attachment_path": attachment_path,
                "notes": notes
            })
            repo.update_batch_item_status(item_id, "已确认")
            flash("企业资质证书成功导入资质库！", "success")
        except Exception as exc:
            flash(f"导入资质失败: {exc}", "danger")

    return redirect(url_for("web.batch"))


@bp.post("/batch/<int:item_id>/delete")
def delete_batch_item(item_id: int):
    item = repo.get_batch_item(item_id)
    if not item:
        flash("批量条目不存在", "danger")
        return redirect(url_for("web.batch"))

    try:
        repo.delete_batch_item(item_id)
        if item["status"] != "已确认":
            _delete_upload_file(item["stored_path"])
        repo.record_audit(
            "delete",
            "batch_item",
            item_id,
            actor_admin_id=_actor_id(),
            details={"source_filename": item["source_filename"]},
        )
        flash("批量上传记录已成功忽略并删除。", "success")
    except Exception as exc:
        flash(f"删除失败: {exc}", "danger")

    return redirect(url_for("web.batch"))


@bp.get("/exports")
def exports():
    return render_template("exports.html")


@bp.get("/exports/<export_type>")
def download_export(export_type: str):
    from io import BytesIO
    from pathlib import Path
    from flask import current_app
    from flask import send_file
    from construction_maintenance.services.exports import (
        build_people_workbook,
        build_project_ledger_workbook,
        build_qualification_workbook,
        build_contract_workbook
    )

    export_dir = Path(current_app.root_path).parent / "exports"
    builders = {
        "project-ledger": ("项目台账.xlsx", build_project_ledger_workbook),
        "people": ("基础人员信息表.xlsx", build_people_workbook),
        "qualifications": ("企业资质清单.xlsx", build_qualification_workbook),
        "contracts": ("项目合同台账.xlsx", build_contract_workbook),
    }
    if export_type not in builders:
        return "Unknown export type", 404
    filename, builder = builders[export_type]
    if export_type == "project-ledger":
        workbook_stream = BytesIO()
        builder(
            workbook_stream,
            project_id=request.args.get("project_id", type=int),
            **_ledger_filters(),
        )
        return send_file(
            workbook_stream,
            as_attachment=True,
            download_name=filename,
        )
    path = builder(export_dir / filename)
    return send_file(path, as_attachment=True, download_name=filename)


@bp.route("/contracts", methods=["GET", "POST"])
def contracts():
    if request.method == "POST":
        attachment_path = _save_form_upload("attachment")
        try:
            repo.create_contract(
                {
                "project_id": int(required_text(request.form, "project_id", "归属项目")),
                "name": required_text(request.form, "name", "合同名称"),
                "contract_type": required_text(request.form, "contract_type", "合同分类"),
                "notes": text_value(request.form, "notes"),
                "attachment_path": attachment_path,
                }
            )
        except Exception:
            _delete_upload_file(attachment_path)
            raise
        flash("新增合同成功。", "success")
        return redirect(url_for("web.contracts"))

    filter_project_id = request.args.get("project_id", type=int)
    filter_contract_type = request.args.get("contract_type")
    search_query = request.args.get("query")

    contracts_list = repo.list_contracts(
        project_id=filter_project_id,
        contract_type=filter_contract_type,
        query=search_query,
    )

    # 计算合同统计指标
    all_c = repo.list_contracts()
    type_stats = {
        "总包合同": sum(1 for c in all_c if c["contract_type"] == "总包合同"),
        "劳务合同": sum(1 for c in all_c if c["contract_type"] == "劳务合同"),
        "材料商合同": sum(1 for c in all_c if c["contract_type"] == "材料商合同"),
        "人员合同": sum(1 for c in all_c if c["contract_type"] == "人员合同"),
        "其它": sum(1 for c in all_c if c["contract_type"] == "其它"),
    }

    return render_template(
        "contracts.html",
        contracts=contracts_list,
        projects=repo.list_projects(),
        filter_project_id=filter_project_id,
        filter_contract_type=filter_contract_type,
        search_query=search_query,
        stats={
            "total": len(all_c),
            **type_stats
        }
    )


@bp.route("/contracts/<int:contract_id>/edit", methods=["POST"])
def edit_contract(contract_id: int):
    existing = repo.get_contract(contract_id)
    if existing is None:
        raise ValueError("合同不存在")
    attachment_path = _save_form_upload("attachment")
    data = {
        "project_id": int(required_text(request.form, "project_id", "归属项目")),
        "name": required_text(request.form, "name", "合同名称"),
        "contract_type": required_text(request.form, "contract_type", "合同分类"),
        "notes": text_value(request.form, "notes"),
    }
    if attachment_path:
        data["attachment_path"] = attachment_path

    try:
        repo.update_contract(contract_id, data)
    except Exception:
        _delete_upload_file(attachment_path)
        raise
    if attachment_path and existing["attachment_path"] != attachment_path:
        _delete_upload_file(existing["attachment_path"])
    flash("合同更新成功。", "success")
    return redirect(
        safe_redirect_target(request.referrer, url_for("web.contracts"))
    )


@bp.route("/contracts/<int:contract_id>/delete", methods=["POST"])
def delete_contract(contract_id: int):
    contract = repo.get_db().execute(
        "select attachment_path, name from contracts where id = ?", (contract_id,)
    ).fetchone()
    if contract is None:
        raise ValueError("合同不存在")
    repo.delete_contract(contract_id)
    _delete_upload_file(contract["attachment_path"])
    repo.record_audit(
        "delete",
        "contract",
        contract_id,
        actor_admin_id=_actor_id(),
        details={"name": contract["name"]},
    )
    flash("合同删除成功。", "success")
    return redirect(url_for("web.contracts"))


@bp.route("/people/<int:person_id>/generate_contract", methods=["POST"])
def generate_person_contract(person_id: int):
    from construction_maintenance.services import contract_generator as cg
    person = repo.get_person(person_id)
    if person is None:
        raise ValueError("人员不存在")
        
    project_id = int(required_text(request.form, "project_id", "归属工程项目"))
    template_id = text_value(request.form, "template_id") or "01_labor_contract"
    
    project = repo.get_project(project_id)
    if project is None:
        raise ValueError("工程项目不存在")

    template_info = cg.get_template_by_id(template_id)
    html_content = cg.render_contract_html(template_id, dict(person), dict(project))
    
    # Save generated HTML to uploads
    file_name = f"generated_contract_{person_id}_{int(time.time())}.html"
    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)
    file_path = upload_folder / file_name
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    contract_name = f"{person['name']}-{template_info['name']}"
    contract_id = repo.create_contract({
        "project_id": project_id,
        "name": contract_name,
        "contract_type": template_info["category"],
        "attachment_path": file_name,
        "notes": f"系统基于档案自动生成；包含人员: {person['name']}({person['job_type']})；请打印/签署后回传原件。",
        "person_id": person_id,
        "status": "待签署",
        "template_name": template_info["name"]
    })

    flash(f"已成功为人员【{person['name']}】自动生成合同，可在线预览或导出。", "success")
    return redirect(url_for("web.people", tab="person_contracts"))


@bp.route("/contracts/<int:contract_id>/upload_signed", methods=["POST"])
def upload_signed_contract(contract_id: int):
    existing = repo.get_contract(contract_id)
    if existing is None:
        raise ValueError("合同不存在")
        
    attachment_path = _save_form_upload("signed_attachment")
    if not attachment_path:
        flash("请选择要上传的已签署合同扫描件/PDF。", "warning")
        return redirect(safe_redirect_target(request.referrer, url_for("web.contracts")))

    data = {
        "project_id": existing["project_id"],
        "name": existing["name"],
        "contract_type": existing["contract_type"],
        "attachment_path": attachment_path,
        "notes": (existing["notes"] or "") + " [已回传签署盖章原件]",
        "status": "已签署"
    }

    try:
        repo.update_contract(contract_id, data)
    except Exception:
        _delete_upload_file(attachment_path)
        raise

    if existing["attachment_path"] and existing["attachment_path"] != attachment_path and not existing["attachment_path"].startswith("generated_contract_"):
        _delete_upload_file(existing["attachment_path"])

    flash("已成功回传归档签署原件！", "success")
    return redirect(safe_redirect_target(request.referrer, url_for("web.contracts")))


@bp.route("/uploads/<path:filename>")
def download_attachment(filename):
    import mimetypes
    from flask import current_app, send_from_directory

    download_name = _download_name_for_upload(filename)
    mimetype = mimetypes.guess_type(download_name)[0] or "application/octet-stream"
    safe_inline = mimetype == "application/pdf" or mimetype.startswith("image/")
    as_attachment = request.args.get("download", "0") == "1" or not safe_inline
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        filename,
        as_attachment=as_attachment,
        download_name=download_name,
        mimetype=mimetype,
    )



@bp.route("/vouchers/<int:voucher_id>/edit", methods=["POST"])
def edit_voucher(voucher_id: int):
    payload = {
        "project_id": int(required_text(request.form, "project_id", "项目")),
        "voucher_date": required_text(request.form, "voucher_date", "日期"),
        "transaction_type": required_text(
            request.form, "transaction_type", "收支类型"
        ),
        "category_id": int(
            required_text(request.form, "category_id", "二级分类")
        ),
        "amount": required_text(request.form, "amount", "金额"),
        "notes": text_value(request.form, "notes"),
        "handler_name": text_value(request.form, "handler_name"),
        "payment_status": required_text(
            request.form, "payment_status", "付款状态"
        ),
        "payment_date": text_value(request.form, "payment_date"),
        "payment_notes": text_value(request.form, "payment_notes"),
        "review_status": text_value(request.form, "review_status") or "已确认",
        "actor_admin_id": _actor_id(),
    }
    repo.update_voucher(voucher_id, payload)
    return redirect(
        safe_redirect_target(request.referrer, url_for("web.vouchers"))
    )


@bp.post("/vouchers/<int:voucher_id>/void")
def void_voucher(voucher_id: int):
    repo.void_voucher(
        voucher_id,
        required_text(request.form, "reason", "作废原因"),
        actor_admin_id=_actor_id(),
    )
    flash("凭证已作废并保留在历史台账中。", "success")
    return redirect(
        safe_redirect_target(request.referrer, url_for("web.vouchers"))
    )


@bp.route("/people/<int:person_id>/edit", methods=["POST"])
def edit_person(person_id: int):
    existing = repo.get_db().execute(
        "select id_card_path from people where id = ?", (person_id,)
    ).fetchone()
    if existing is None:
        raise ValueError("人员不存在")
    attachment_path = _save_form_upload("id_card_attachment")
    try:
        repo.update_person(
            person_id,
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
                "id_card_path": attachment_path,
                "is_attendance": 1 if request.form.get("is_attendance") else 0,
                "salary_type": text_value(request.form, "salary_type") or "日薪",
                "salary_rate": float(text_value(request.form, "salary_rate") or 0.0),
            }
        )
        if attachment_path and existing["id_card_path"] != attachment_path:
            _delete_upload_file(existing["id_card_path"])
        flash("人员档案已成功修改。", "success")
    except sqlite3.IntegrityError:
        _delete_upload_file(attachment_path)
        flash("修改失败：该身份证号已被登记。", "danger")
    except Exception:
        _delete_upload_file(attachment_path)
        raise
    return redirect(url_for("web.people"))


@bp.route("/people/<int:person_id>/delete", methods=["POST"])
def delete_person(person_id: int):
    person = repo.get_db().execute(
        "select id_card_path, name from people where id = ?", (person_id,)
    ).fetchone()
    if person is None:
        raise ValueError("人员不存在")
    try:
        repo.delete_person(person_id)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("web.people"))
    _delete_upload_file(person["id_card_path"])
    repo.record_audit(
        "delete",
        "person",
        person_id,
        actor_admin_id=_actor_id(),
        details={"name": person["name"]},
    )
    flash("人员电子档案已成功删除。", "success")
    return redirect(url_for("web.people"))


@bp.route("/people/<int:person_id>/salary-sheets", methods=["GET"])
def get_person_salary_sheets(person_id: int):
    person = next((p for p in repo.list_people() if int(p["id"]) == person_id), None)
    if not person:
        return {"status": "error", "message": "人员不存在"}, 404
    
    sheets = repo.list_salary_sheets_by_person(person_id)
    return {
        "status": "success",
        "person_name": person["name"],
        "salary_rate": person["salary_rate"],
        "salary_type": person["salary_type"],
        "data": sheets
    }


@bp.route("/people/<int:person_id>/salary-sheets/add", methods=["POST"])
def add_person_salary_sheet(person_id: int):
    person = next((p for p in repo.list_people() if int(p["id"]) == person_id), None)
    if not person:
        return {"status": "error", "message": "人员不存在"}, 404
        
    data = request.get_json() or {}
    settle_month = data.get("settle_month", "").strip()
    if not settle_month:
        return {"status": "error", "message": "结算月份不能为空"}, 400
        
    try:
        settle_month, _, _ = _parse_month(settle_month)
        should_work = float(data.get("should_work_days", 30))
        actual_work = float(data.get("actual_work_days", 30))
        rate = float(data.get("salary_rate", 0.0))
        earnings = float(data.get("earnings", 0.0))
        paid = float(data.get("paid_amount", 0.0))
    except (TypeError, ValueError):
        return {"status": "error", "message": "天数或金额格式不正确"}, 400
        
    repo.create_salary_sheet_item({
        "person_id": person_id,
        "settle_month": settle_month,
        "should_work_days": should_work,
        "actual_work_days": actual_work,
        "salary_rate": rate,
        "earnings": earnings,
        "paid_amount": paid,
        "notes": data.get("notes", "").strip(),
        "actor_admin_id": _actor_id(),
    })
    
    sheets = repo.list_salary_sheets_by_person(person_id)
    return {"status": "success", "data": sheets}


@bp.route("/people/salary-sheets/<int:item_id>/delete", methods=["POST"])
def delete_person_salary_sheet_item(item_id: int):
    db = repo.get_db()
    row = db.execute("select person_id from salary_sheets where id = ?", (item_id,)).fetchone()
    if not row:
        return {"status": "error", "message": "记录不存在"}, 404
    person_id = row[0]
    
    repo.delete_salary_sheet_item(item_id)
    repo.record_audit(
        "delete",
        "salary_sheet",
        item_id,
        actor_admin_id=_actor_id(),
        details={"person_id": person_id},
    )
    
    sheets = repo.list_salary_sheets_by_person(person_id)
    return {"status": "success", "data": sheets}


@bp.route("/attendance/quick-fill-person", methods=["POST"])
def quick_fill_person_attendance():
    data = request.get_json() or {}
    person_id = data.get("person_id")
    month = data.get("month")
    
    if not person_id or not month:
        return {"status": "error", "message": "必要参数缺失"}, 400
        
    try:
        day_shifts = int(data.get("day_shifts", 0))
        night_shifts = int(data.get("night_shifts", 0))
        leave_shifts = int(data.get("leave_shifts", 0))
        skip_weekends = bool(data.get("skip_weekends", True))
    except (TypeError, ValueError):
        return {"status": "error", "message": "天数参数必须为整数"}, 400
        
    try:
        import calendar
        import datetime
        
        person_id = int(person_id)
        month, year, m = _parse_month(month)
        if min(day_shifts, night_shifts, leave_shifts) < 0:
            raise ValueError("天数不能为负数")
        _, num_days = calendar.monthrange(year, m)
        
        workdays = []
        weekends = []
        for d in range(1, num_days + 1):
            date_str = f"{month}-{d:02d}"
            dt = datetime.date(year, m, d)
            if dt.weekday() in (5, 6):
                weekends.append(date_str)
            else:
                workdays.append(date_str)
                
        if skip_weekends:
            target_dates = workdays + weekends
        else:
            target_dates = [f"{month}-{d:02d}" for d in range(1, num_days + 1)]
            
        shifts_pool = (
            ["上班"] * (day_shifts + night_shifts) + 
            ["请假"] * leave_shifts
        )
        
        if len(shifts_pool) > num_days:
            return {"status": "error", "message": f"填充的总天数 ({len(shifts_pool)} 天) 超过了当月的总天数 ({num_days} 天)"}, 400
            
        db = repo.get_db()
        db.execute(
            "delete from attendance where person_id = ? and work_date like ?",
            (person_id, f"{month}-%"),
        )
        
        for idx, shift in enumerate(shifts_pool):
            date_str = target_dates[idx]
            db.execute(
                """
                insert into attendance (person_id, work_date, shift_type)
                values (?, ?, ?)
                """,
                (person_id, date_str, shift),
            )
            
        db.commit()
        return {"status": "success"}
    except (TypeError, ValueError, sqlite3.IntegrityError) as exc:
        return {"status": "error", "message": str(exc)}, 400


@bp.route("/qualifications/<int:qualification_id>/edit", methods=["POST"])
def edit_qualification(qualification_id: int):
    existing = repo.get_db().execute(
        "select attachment_path from qualifications where id = ?",
        (qualification_id,),
    ).fetchone()
    if existing is None:
        raise ValueError("资质证书不存在")
    company_id = int(required_text(request.form, "company_id", "公司"))
    from pathlib import Path
    from flask import current_app
    from construction_maintenance.services.imports import save_upload
    
    data = {
        "company_id": company_id,
        "name": required_text(request.form, "name", "资质名称"),
        "certificate_no": required_text(request.form, "certificate_no", "证书编号"),
        "issue_date": text_value(request.form, "issue_date"),
        "expiry_date": text_value(request.form, "expiry_date"),
        "is_long_term": 1 if request.form.get("is_long_term") else 0,
        "notes": text_value(request.form, "notes"),
    }
    
    file = request.files.get("attachment")
    if file and file.filename:
        upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
        stored = save_upload(upload_folder, file)
        data["attachment_path"] = stored.name
        
    try:
        repo.update_qualification(qualification_id, data)
    except Exception:
        _delete_upload_file(data.get("attachment_path"))
        raise
    if data.get("attachment_path") and existing["attachment_path"] != data["attachment_path"]:
        _delete_upload_file(existing["attachment_path"])
    return redirect(url_for("web.qualifications"))


@bp.route("/qualifications/<int:qualification_id>/delete", methods=["POST"])
def delete_qualification(qualification_id: int):
    qualification = repo.get_db().execute(
        "select attachment_path, name from qualifications where id = ?",
        (qualification_id,),
    ).fetchone()
    if qualification is None:
        raise ValueError("资质证书不存在")
    repo.delete_qualification(qualification_id)
    _delete_upload_file(qualification["attachment_path"])
    repo.record_audit(
        "delete",
        "qualification",
        qualification_id,
        actor_admin_id=_actor_id(),
        details={"name": qualification["name"]},
    )
    flash("资质证书已成功删除。", "success")
    return redirect(url_for("web.qualifications"))


@bp.route("/companies/<int:company_id>/edit", methods=["POST"])
def edit_company(company_id: int):
    data = {
        "name": required_text(request.form, "name", "公司名称"),
        "credit_code": text_value(request.form, "credit_code"),
        "legal_person": text_value(request.form, "legal_person"),
        "phone": text_value(request.form, "phone"),
        "notes": text_value(request.form, "notes"),
    }
    try:
        repo.update_company(company_id, data)
        flash("合作单位信息已成功修改。", "success")
    except sqlite3.IntegrityError:
        flash("修改失败：该公司名称已存在。", "danger")
    return redirect(url_for("web.qualifications"))


@bp.route("/companies/add", methods=["POST"])
def add_company():
    data = {
        "name": required_text(request.form, "name", "公司名称"),
        "credit_code": text_value(request.form, "credit_code"),
        "legal_person": text_value(request.form, "legal_person"),
        "phone": text_value(request.form, "phone"),
        "notes": text_value(request.form, "notes"),
        "is_main": 0,
    }
    try:
        repo.create_company(data)
        flash("合作单位已成功添加。", "success")
    except sqlite3.IntegrityError:
        flash("添加失败：该公司名称已存在。", "danger")
    return redirect(url_for("web.qualifications"))


@bp.route("/companies/<int:company_id>/delete", methods=["POST"])
def delete_company(company_id: int):
    db = repo.get_db()
    company = db.execute("select * from companies where id = ?", (company_id,)).fetchone()
    if not company:
        flash("单位不存在", "danger")
        return redirect(url_for("web.qualifications"))
    if company["is_main"] == 1:
        flash("主公司为系统核心单位，不支持删除。", "danger")
        return redirect(url_for("web.qualifications"))
        
    projects_count = db.execute("select count(*) from projects where company_id = ?", (company_id,)).fetchone()[0]
    quals_count = db.execute("select count(*) from qualifications where company_id = ?", (company_id,)).fetchone()[0]
    
    if projects_count > 0 or quals_count > 0:
        flash("无法删除该单位：该单位名下已有关联绑定的工程项目或企业资质。请先删除或转移对应的项目与资质后再试。", "danger")
        return redirect(url_for("web.qualifications"))
        
    repo.delete_company(company_id)
    flash("单位已成功删除。", "success")
    return redirect(url_for("web.qualifications"))



@bp.route("/qualifications/recognize", methods=["POST"])
def recognize_qualification():
    from flask import current_app, jsonify
    from pathlib import Path
    from construction_maintenance.services.imports import save_upload

    file = request.files.get("attachment")
    if not file or not file.filename:
        return jsonify({"success": False, "error": "没有上传文件"}), 400
    if not current_app.config.get("ARK_API_KEY"):
        return jsonify({"success": False, "error": "AI 识别服务未配置，请人工录入"}), 503

    stored = save_upload(Path(current_app.config["UPLOAD_FOLDER"]), file)
    try:
        ocr_result = recognize_batch_upload(stored, "qualification")
    finally:
        stored.unlink(missing_ok=True)

    if ocr_result.status != "已识别":
        message = str(ocr_result.data.get("message") or "AI 识别失败，请人工录入")
        return jsonify({"success": False, "error": message}), 422

    result = ocr_result.data
    data = {
        "name_select": result.get("name_select") or "CUSTOM",
        "certificate_no": result.get("certificate_no") or "",
        "credit_code": result.get("credit_code") or "",
        "legal_person": result.get("legal_person") or "",
        "issue_date": result.get("issue_date") or "",
        "expiry_date": result.get("expiry_date") or "",
        "is_long_term": bool(result.get("is_long_term")),
        "notes": result.get("notes") or "",
        "company_name": result.get("company_name") or "",
    }
    return jsonify({"success": True, "data": data})
