from __future__ import annotations

import sqlite3
import re
import math
from datetime import date
import json
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from .db import DEFAULT_SYSTEM_SETTINGS, get_db
from .finance import (
    CLASSIFICATION_CONFIDENCES,
    LEGACY_CATEGORY_MAP,
    PAYMENT_STATUSES,
    REVIEW_STATUSES,
    TRANSACTION_TYPES,
)


PASSWORD_MIN_LENGTH = 12
ADMIN_ROLES = {"admin", "super_admin"}
ADMIN_USERNAME_PATTERN = re.compile(r"^[\w.@-]+$", re.UNICODE)
ID_NUMBER_PATTERN = re.compile(r"^\d{17}[\dXx]$")
PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")
PROJECT_STATUSES = {"进行中", "已暂停", "已完工"}


def _required_text(value: Any, label: str, *, max_length: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label}不能为空")
    if len(text) > max_length:
        raise ValueError(f"{label}不能超过 {max_length} 个字符")
    return text


def _validated_date(value: Any, label: str, *, required: bool = False) -> str:
    text = str(value or "").strip()
    if not text:
        if required:
            raise ValueError(f"{label}不能为空")
        return ""
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label}格式无效") from exc
    return text


def _validated_month(value: Any, label: str = "月份") -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", text):
        raise ValueError(f"{label}格式无效，请使用 YYYY-MM")
    return text


def _validated_id_number(value: Any) -> str:
    number = _required_text(value, "身份证号", max_length=18).upper()
    if not ID_NUMBER_PATTERN.fullmatch(number):
        raise ValueError("身份证号必须为 18 位有效格式")
    try:
        date.fromisoformat(f"{number[6:10]}-{number[10:12]}-{number[12:14]}")
    except ValueError as exc:
        raise ValueError("身份证号中的出生日期无效") from exc
    return number


def _validated_phone(value: Any) -> str:
    phone = str(value or "").strip()
    if phone and not PHONE_PATTERN.fullmatch(phone):
        raise ValueError("手机号必须为 11 位中国大陆手机号码")
    return phone


def _insert_audit(
    db,
    *,
    actor_admin_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    details: dict[str, Any] | str | None = None,
) -> None:
    if isinstance(details, dict):
        details_text = json.dumps(details, ensure_ascii=False, sort_keys=True)
    else:
        details_text = str(details or "")
    db.execute(
        """
        insert into audit_events (
            actor_admin_id, action, entity_type, entity_id, details
        ) values (?, ?, ?, ?, ?)
        """,
        (actor_admin_id, action, entity_type, entity_id, details_text),
    )


def record_audit(
    action: str,
    entity_type: str,
    entity_id: int | None,
    *,
    actor_admin_id: int | None = None,
    details: dict[str, Any] | str | None = None,
) -> None:
    db = get_db()
    _insert_audit(
        db,
        actor_admin_id=actor_admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.commit()


def list_audit_events(limit: int = 200):
    return get_db().execute(
        """
        select audit_events.*, admin_users.display_name as actor_name
        from audit_events
        left join admin_users on admin_users.id = audit_events.actor_admin_id
        order by audit_events.id desc
        limit ?
        """,
        (max(1, min(int(limit), 1000)),),
    ).fetchall()


def login_attempt_is_locked(attempt_key: str, now: int) -> bool:
    row = get_db().execute(
        "select locked_until from login_attempts where attempt_key = ?",
        (attempt_key,),
    ).fetchone()
    return bool(row and int(row["locked_until"]) > now)


def record_login_failure(
    attempt_key: str,
    now: int,
    *,
    max_failures: int = 5,
    window_seconds: int = 900,
    lock_seconds: int = 900,
) -> bool:
    db = get_db()
    row = db.execute(
        "select * from login_attempts where attempt_key = ?",
        (attempt_key,),
    ).fetchone()
    if row is None or now - int(row["first_failure_at"]) > window_seconds:
        failures = 1
        first_failure_at = now
    else:
        failures = int(row["failures"]) + 1
        first_failure_at = int(row["first_failure_at"])
    locked_until = now + lock_seconds if failures >= max_failures else 0
    db.execute(
        """
        insert into login_attempts (
            attempt_key, failures, first_failure_at, locked_until
        ) values (?, ?, ?, ?)
        on conflict(attempt_key) do update set
            failures = excluded.failures,
            first_failure_at = excluded.first_failure_at,
            locked_until = excluded.locked_until
        """,
        (attempt_key, failures, first_failure_at, locked_until),
    )
    db.commit()
    return locked_until > now


def clear_login_failures(attempt_key: str) -> None:
    db = get_db()
    db.execute("delete from login_attempts where attempt_key = ?", (attempt_key,))
    db.commit()


def _normalized_admin_username(value: Any) -> str:
    username = str(value or "").strip()
    if not 3 <= len(username) <= 50:
        raise ValueError("用户名长度须为 3 至 50 个字符")
    if not ADMIN_USERNAME_PATTERN.fullmatch(username):
        raise ValueError("用户名仅可包含字母、数字、中文、点、短横线和下划线")
    return username


def _validated_password(value: Any) -> str:
    password = str(value or "")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"密码长度不能少于 {PASSWORD_MIN_LENGTH} 位")
    return password


def _validated_admin_role(value: Any) -> str:
    role = str(value or "")
    if role not in ADMIN_ROLES:
        raise ValueError("管理员角色无效")
    return role


def get_admin_user(user_id: int):
    return get_db().execute(
        "select * from admin_users where id = ?", (user_id,)
    ).fetchone()


def get_admin_user_by_username(username: str):
    return get_db().execute(
        "select * from admin_users where username = ?",
        (str(username or "").strip(),),
    ).fetchone()


def authenticate_admin_user(username: str, password: str):
    user = get_admin_user_by_username(username)
    if (
        user is None
        or not user["is_active"]
        or not check_password_hash(user["password_hash"], password)
    ):
        return None

    db = get_db()
    db.execute(
        """
        update admin_users
        set last_login_at = current_timestamp
        where id = ?
        """,
        (user["id"],),
    )
    db.commit()
    return get_admin_user(user["id"])


def list_admin_users():
    return get_db().execute(
        """
        select *
        from admin_users
        order by
            case role when 'super_admin' then 0 else 1 end,
            is_active desc,
            username collate nocase
        """
    ).fetchall()


def count_active_super_admins() -> int:
    return int(
        get_db()
        .execute(
            """
            select count(*)
            from admin_users
            where role = 'super_admin' and is_active = 1
            """
        )
        .fetchone()[0]
    )


def create_admin_user(data: dict[str, Any]) -> int:
    username = _normalized_admin_username(data.get("username"))
    display_name = str(data.get("display_name") or "").strip() or username
    if len(display_name) > 50:
        raise ValueError("显示名称不能超过 50 个字符")
    password = _validated_password(data.get("password"))
    role = _validated_admin_role(data.get("role", "admin"))
    is_active = 1 if data.get("is_active", True) else 0

    try:
        cursor = get_db().execute(
            """
            insert into admin_users (
                username, display_name, password_hash, role, is_active,
                must_change_password
            )
            values (?, ?, ?, ?, ?, 1)
            """,
            (
                username,
                display_name,
                generate_password_hash(password),
                role,
                is_active,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("该管理员用户名已存在") from exc
    get_db().commit()
    return int(cursor.lastrowid)


def update_admin_user(
    user_id: int, data: dict[str, Any], *, actor_id: int
) -> None:
    db = get_db()
    existing = get_admin_user(user_id)
    if existing is None:
        raise ValueError("管理员账号不存在")

    display_name = str(data.get("display_name") or "").strip()
    if not display_name:
        raise ValueError("显示名称不能为空")
    if len(display_name) > 50:
        raise ValueError("显示名称不能超过 50 个字符")
    role = _validated_admin_role(data.get("role"))
    is_active = 1 if data.get("is_active") else 0

    if user_id == actor_id and (role != "super_admin" or not is_active):
        raise ValueError("不能停用自己或降低自己的权限")
    removes_active_super_admin = (
        existing["role"] == "super_admin"
        and existing["is_active"]
        and (role != "super_admin" or not is_active)
    )
    if removes_active_super_admin and count_active_super_admins() <= 1:
        raise ValueError("系统必须保留至少一名启用中的超级管理员")

    db.execute(
        """
        update admin_users
        set display_name = ?, role = ?, is_active = ?,
            updated_at = current_timestamp
        where id = ?
        """,
        (display_name, role, is_active, user_id),
    )
    db.commit()


def reset_admin_password(user_id: int, password: Any) -> None:
    if get_admin_user(user_id) is None:
        raise ValueError("管理员账号不存在")
    password = _validated_password(password)
    get_db().execute(
        """
        update admin_users
        set password_hash = ?, must_change_password = 1,
            updated_at = current_timestamp
        where id = ?
        """,
        (generate_password_hash(password), user_id),
    )
    get_db().commit()


def change_own_password(
    user_id: int, current_password: str, new_password: str
) -> None:
    user = get_admin_user(user_id)
    if user is None or not check_password_hash(
        user["password_hash"], str(current_password or "")
    ):
        raise ValueError("当前密码不正确")
    new_password = _validated_password(new_password)
    if check_password_hash(user["password_hash"], new_password):
        raise ValueError("新密码不能与当前密码相同")
    get_db().execute(
        """
        update admin_users
        set password_hash = ?, must_change_password = 0,
            updated_at = current_timestamp
        where id = ?
        """,
        (generate_password_hash(new_password), user_id),
    )
    get_db().commit()


def get_system_settings() -> dict[str, str]:
    settings = dict(DEFAULT_SYSTEM_SETTINGS)
    rows = get_db().execute("select key, value from system_settings").fetchall()
    settings.update({row["key"]: row["value"] for row in rows})
    return settings


def get_system_setting(key: str) -> str:
    return get_system_settings().get(key, DEFAULT_SYSTEM_SETTINGS.get(key, ""))


def update_system_settings(values: dict[str, str]) -> None:
    db = get_db()
    for key in DEFAULT_SYSTEM_SETTINGS:
        if key not in values:
            continue
        db.execute(
            """
            insert into system_settings (key, value, updated_at)
            values (?, ?, current_timestamp)
            on conflict(key) do update set
                value = excluded.value,
                updated_at = current_timestamp
            """,
            (key, str(values[key])),
        )
    db.commit()


def normalize_amount(value: Any) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("金额必须是数字") from exc
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("金额必须大于 0")
    return amount


def normalize_expense_category_name(value: Any) -> str:
    name = str(value or "").strip()
    if not name:
        raise ValueError("费用科目名称不能为空")
    return name


def normalize_sort_order(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _validated_choice(value: Any, label: str, choices: tuple[str, ...]) -> str:
    text = str(value or "").strip()
    if text not in choices:
        raise ValueError(f"{label}无效")
    return text


def _get_leaf_category(category_id: int):
    row = get_db().execute(
        """
        select leaf.*, parent.name as primary_name
        from expense_categories leaf
        join expense_categories parent on parent.id = leaf.parent_id
        where leaf.id = ? and leaf.is_active = 1 and parent.is_active = 1
        """,
        (int(category_id),),
    ).fetchone()
    if row is None:
        raise ValueError("二级分类不存在或已停用")
    return row


def _insert_voucher(db: sqlite3.Connection, data: dict[str, Any]) -> int:
    amount = normalize_amount(data["amount"])
    voucher_date = _validated_date(data.get("voucher_date"), "凭证日期", required=True)
    transaction_type = _validated_choice(
        data.get("transaction_type", "支出"), "收支类型", TRANSACTION_TYPES
    )
    category = _get_leaf_category(int(data["category_id"]))
    expected_scope = "支出" if transaction_type in {"支出", "冲减支出"} else transaction_type
    if category["transaction_scope"] != expected_scope:
        raise ValueError("分类与收支类型不匹配")
    payment_status = _validated_choice(
        data.get("payment_status", "支付状态待确认"), "付款状态", PAYMENT_STATUSES
    )
    review_status = _validated_choice(
        data.get("review_status", "已确认"), "复核状态", REVIEW_STATUSES
    )
    confidence = str(data.get("classification_confidence") or "").strip()
    if confidence and confidence not in CLASSIFICATION_CONFIDENCES:
        raise ValueError("分类置信度无效")
    cursor = db.execute(
        """
        insert into vouchers (
          project_id, voucher_date, voucher_type, amount, notes, attachment_path,
          entry_user, source_record_id, transaction_type, category_id, handler_name,
          payment_status, payment_date, payment_notes, review_status,
          classification_confidence, source_filename, source_sheet, source_row,
          original_notes
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(data["project_id"]), voucher_date,
            str(data.get("voucher_type") or category["name"]), amount,
            str(data.get("notes") or ""), str(data.get("attachment_path") or ""),
            str(data.get("entry_user") or ""), data.get("source_record_id"),
            transaction_type, category["id"], str(data.get("handler_name") or ""),
            payment_status, _validated_date(data.get("payment_date"), "付款日期"),
            str(data.get("payment_notes") or ""), review_status, confidence,
            str(data.get("source_filename") or ""), str(data.get("source_sheet") or ""),
            data.get("source_row"), str(data.get("original_notes") or ""),
        ),
    )
    return int(cursor.lastrowid)


def list_expense_categories(include_inactive: bool = False):
    where = "" if include_inactive else "where categories.is_active = 1"
    return get_db().execute(
        f"""
        select categories.*, parents.name as primary_name,
               (select count(*) from expense_categories children where children.parent_id = categories.id) as child_count,
               (select count(*) from vouchers where vouchers.category_id = categories.id) as voucher_count,
               (select count(*) from ledger_pending_items pending where pending.suggested_category_id = categories.id and pending.status = '待补录') as pending_count
        from expense_categories categories
        left join expense_categories parents on parents.id = categories.parent_id
        {where}
        order by categories.sort_order, categories.id
        """
    ).fetchall()


def list_expense_category_names(include_inactive: bool = False) -> list[str]:
    return [row["name"] for row in list_expense_categories(include_inactive=include_inactive)]


def list_voucher_type_names(project_id: int | None = None) -> list[str]:
    params: list[Any] = []
    conditions = ["is_void = 0"]
    if project_id:
        conditions.append("project_id = ?")
        params.append(project_id)
    where = "where " + " and ".join(conditions)
    rows = get_db().execute(
        f"""
        select distinct coalesce(secondary.name, vouchers.voucher_type) as voucher_type
        from vouchers
        left join expense_categories secondary on secondary.id = vouchers.category_id
        {where}
        order by voucher_type
        """,
        params,
    ).fetchall()
    return [row["voucher_type"] for row in rows]


def create_expense_category(data: dict[str, Any]) -> int:
    db = get_db()
    name = normalize_expense_category_name(data["name"])
    sort_order = normalize_sort_order(data.get("sort_order"))
    parent_id = data.get("parent_id")
    if "parent_id" not in data:
        fallback_parent = db.execute(
            "select id from expense_categories where name = '财务及其他' and parent_id is null"
        ).fetchone()
        parent_id = fallback_parent["id"] if fallback_parent else None
    submitted_scope = str(data.get("transaction_scope") or "").strip()
    if parent_id is not None:
        parent = db.execute(
            """
            select * from expense_categories
            where id = ? and parent_id is null and is_active = 1
            """,
            (int(parent_id),),
        ).fetchone()
        if parent is None:
            raise ValueError("所属分类必须是启用的一级分类")
        if submitted_scope and submitted_scope != parent["transaction_scope"]:
            raise ValueError("分类与收支范围不匹配")
        transaction_scope = str(parent["transaction_scope"])
    else:
        transaction_scope = submitted_scope or "支出"
    if transaction_scope not in {"支出", "收入", "资金往来"}:
        raise ValueError("收支范围无效")
    try:
        cursor = db.execute(
            """
            insert into expense_categories
              (name, parent_id, transaction_scope, sort_order, is_active)
            values (?, ?, ?, ?, 1)
            """,
            (name, parent_id, transaction_scope, sort_order),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("费用科目名称不能重复") from exc
    db.commit()
    return int(cursor.lastrowid)


def update_expense_category(category_id: int, data: dict[str, Any]) -> None:
    db = get_db()
    existing = db.execute("select * from expense_categories where id = ?", (category_id,)).fetchone()
    if existing is None:
        raise ValueError("费用科目不存在")

    name = normalize_expense_category_name(data["name"])
    sort_order = normalize_sort_order(data.get("sort_order"))
    is_active = 1 if data.get("is_active") else 0
    parent_id = data.get("parent_id", existing["parent_id"])
    transaction_scope = str(
        data.get("transaction_scope") or existing["transaction_scope"] or "支出"
    )
    if transaction_scope not in {"支出", "收入", "资金往来"}:
        raise ValueError("收支范围无效")
    if (
        existing["parent_id"] is None
        and transaction_scope != existing["transaction_scope"]
    ):
        child_count = db.execute(
            "select count(*) from expense_categories where parent_id = ?",
            (category_id,),
        ).fetchone()[0]
        if child_count:
            raise ValueError("一级分类仍有二级分类，不能修改收支范围")
    if parent_id is not None and int(parent_id) == category_id:
        raise ValueError("分类不能以自身为父分类")
    if parent_id is not None:
        parent = db.execute(
            """
            select * from expense_categories
            where id = ? and parent_id is null and is_active = 1
            """,
            (int(parent_id),),
        ).fetchone()
        if parent is None:
            raise ValueError("一级分类不存在或已停用")
        if parent["transaction_scope"] != transaction_scope:
            raise ValueError("分类与收支范围不匹配")

    try:
        db.execute(
            """
            update expense_categories
            set name = ?, parent_id = ?, transaction_scope = ?,
                sort_order = ?, is_active = ?
            where id = ?
            """,
            (name, parent_id, transaction_scope, sort_order, is_active, category_id),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("费用科目名称不能重复") from exc

    if existing["name"] != name:
        db.execute(
            """
            update vouchers
            set voucher_type = ?
            where category_id = ? or voucher_type = ?
            """,
            (name, category_id, existing["name"]),
        )
    db.commit()


def get_main_company():
    return get_db().execute("select * from companies where is_main = 1").fetchone()


def list_companies():
    return get_db().execute("select * from companies order by is_main desc, name").fetchall()


def create_company(data: dict[str, Any]) -> int:
    cursor = get_db().execute(
        """
        insert into companies (name, credit_code, legal_person, phone, notes, is_main)
        values (?, ?, ?, ?, ?, ?)
        """,
        (
            data["name"],
            data.get("credit_code", ""),
            data.get("legal_person", ""),
            data.get("phone", ""),
            data.get("notes", ""),
            int(data.get("is_main", 0)),
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)


def update_company(company_id: int, data: dict[str, Any]) -> None:
    get_db().execute(
        """
        update companies
        set name = ?, credit_code = ?, legal_person = ?, phone = ?, notes = ?
        where id = ?
        """,
        (
            data["name"],
            data.get("credit_code", ""),
            data.get("legal_person", ""),
            data.get("phone", ""),
            data.get("notes", ""),
            company_id,
        ),
    )
    get_db().commit()


def delete_company(company_id: int) -> None:
    get_db().execute("delete from companies where id = ?", (company_id,))
    get_db().commit()


def list_projects():
    return get_db().execute(
        """
        select projects.*, companies.name as company_name
        from projects
        join companies on companies.id = projects.company_id
        order by 
            case projects.status 
                when '进行中' then 1 
                when '已暂停' then 2 
                when '已完工' then 3 
                else 4 
            end asc,
            projects.created_at desc
        """
    ).fetchall()


def create_project(data: dict[str, Any]) -> int:
    name = _required_text(data.get("name"), "项目名称")
    status = str(data.get("status") or "进行中")
    if status not in PROJECT_STATUSES:
        raise ValueError("项目状态无效")
    start_date = _validated_date(data.get("start_date"), "开工日期")
    end_date = _validated_date(data.get("end_date"), "完工日期")
    if start_date and end_date and end_date < start_date:
        raise ValueError("完工日期不能早于开工日期")
    cursor = get_db().execute(
        """
        insert into projects (company_id, name, status, owner, start_date, end_date, notes)
        values (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["company_id"],
            name,
            status,
            data.get("owner", ""),
            start_date,
            end_date,
            data.get("notes", ""),
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)


def _voucher_filter_clause(
    project_id: int | None = None,
    *,
    include_voided: bool = False,
    transaction_type: str | None = None,
    primary_category_id: int | None = None,
    category_id: int | None = None,
    payment_status: str | None = None,
    review_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[str, list[Any]]:
    params: list[Any] = []
    conditions: list[str] = []
    filters = (
        (project_id, "vouchers.project_id = ?"),
        (transaction_type, "vouchers.transaction_type = ?"),
        (primary_category_id, "parent.id = ?"),
        (category_id, "leaf.id = ?"),
        (payment_status, "vouchers.payment_status = ?"),
        (review_status, "vouchers.review_status = ?"),
    )
    for value, condition in filters:
        if value not in (None, ""):
            conditions.append(condition)
            params.append(value)
    if date_from:
        conditions.append("vouchers.voucher_date >= ?")
        params.append(_validated_date(date_from, "开始日期", required=True))
    if date_to:
        conditions.append("vouchers.voucher_date <= ?")
        params.append(_validated_date(date_to, "结束日期", required=True))
    if not include_voided:
        conditions.append("vouchers.is_void = 0")
    where = "where " + " and ".join(conditions) if conditions else ""
    return where, params


def list_vouchers(
    project_id: int | None = None,
    *,
    include_voided: bool = False,
    transaction_type: str | None = None,
    primary_category_id: int | None = None,
    category_id: int | None = None,
    payment_status: str | None = None,
    review_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    where, params = _voucher_filter_clause(
        project_id,
        include_voided=include_voided,
        transaction_type=transaction_type,
        primary_category_id=primary_category_id,
        category_id=category_id,
        payment_status=payment_status,
        review_status=review_status,
        date_from=date_from,
        date_to=date_to,
    )
    pagination_sql = ""
    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("分页条数无效") from exc
        if limit <= 0:
            raise ValueError("分页条数必须大于 0")
        pagination_sql = " limit ?"
        params.append(limit)
    try:
        offset = int(offset)
    except (TypeError, ValueError) as exc:
        raise ValueError("分页偏移无效") from exc
    if offset < 0:
        raise ValueError("分页偏移不能小于 0")
    if offset:
        if limit is None:
            pagination_sql = " limit -1"
        pagination_sql += " offset ?"
        params.append(offset)
    return get_db().execute(
        f"""
        select vouchers.*, projects.name as project_name,
               leaf.name as secondary_category,
               parent.name as primary_category,
               parent.id as primary_category_id
        from vouchers
        join projects on projects.id = vouchers.project_id
        left join expense_categories leaf on leaf.id = vouchers.category_id
        left join expense_categories parent on parent.id = leaf.parent_id
        {where}
        order by vouchers.voucher_date desc, vouchers.id desc
        {pagination_sql}
        """,
        params,
    ).fetchall()


def count_vouchers(
    project_id: int | None = None,
    *,
    include_voided: bool = False,
    transaction_type: str | None = None,
    primary_category_id: int | None = None,
    category_id: int | None = None,
    payment_status: str | None = None,
    review_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> int:
    where, params = _voucher_filter_clause(
        project_id,
        include_voided=include_voided,
        transaction_type=transaction_type,
        primary_category_id=primary_category_id,
        category_id=category_id,
        payment_status=payment_status,
        review_status=review_status,
        date_from=date_from,
        date_to=date_to,
    )
    return int(get_db().execute(
        f"""
        select count(*)
        from vouchers
        left join expense_categories leaf on leaf.id = vouchers.category_id
        left join expense_categories parent on parent.id = leaf.parent_id
        {where}
        """,
        params,
    ).fetchone()[0])


def get_voucher(voucher_id: int):
    return get_db().execute(
        "select * from vouchers where id = ?", (voucher_id,)
    ).fetchone()


def create_voucher(data: dict[str, Any]) -> int:
    data = dict(data)
    if not data.get("category_id"):
        legacy_name = _required_text(data.get("voucher_type"), "凭证类型")
        leaf_name = LEGACY_CATEGORY_MAP.get(legacy_name, legacy_name)
        leaf = get_db().execute(
            """
            select id from expense_categories
            where name = ? and parent_id is not null and is_active = 1
            """,
            (leaf_name,),
        ).fetchone()
        if leaf is None:
            raise ValueError("凭证类型没有对应的启用二级分类")
        data["category_id"] = int(leaf["id"])
    db = get_db()
    voucher_id = _insert_voucher(db, data)
    _insert_audit(
        db,
        actor_admin_id=data.get("actor_admin_id"),
        action="create",
        entity_type="voucher",
        entity_id=voucher_id,
        details={
            "amount": data["amount"],
            "voucher_date": data.get("voucher_date"),
            "type": data.get("transaction_type", "支出"),
        },
    )
    db.commit()
    return voucher_id


def get_project_financial_summary(
    project_id: int | None = None,
    *,
    transaction_type: str | None = None,
    primary_category_id: int | None = None,
    category_id: int | None = None,
    payment_status: str | None = None,
    review_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, float | int]:
    where, params = _voucher_filter_clause(
        project_id,
        transaction_type=transaction_type,
        primary_category_id=primary_category_id,
        category_id=category_id,
        payment_status=payment_status,
        review_status=review_status,
        date_from=date_from,
        date_to=date_to,
    )
    row = get_db().execute(
        f"""
        select
          coalesce(sum(case when transaction_type = '支出' then amount else 0 end), 0) as expense,
          coalesce(sum(case when transaction_type = '冲减支出' then amount else 0 end), 0) as expense_reduction,
          coalesce(sum(case when transaction_type = '收入' then amount else 0 end), 0) as income,
          coalesce(sum(case when transaction_type = '资金往来' then amount else 0 end), 0) as fund_transfer,
          coalesce(sum(case
            when payment_status != '已支付/已报销' and transaction_type = '支出' then amount
            when payment_status != '已支付/已报销' and transaction_type = '冲减支出' then -amount
            else 0 end), 0) as unsettled,
          count(*) as entry_count,
          sum(case when review_status = '待复核' then 1 else 0 end) as review_count
        from vouchers
        left join expense_categories leaf on leaf.id = vouchers.category_id
        left join expense_categories parent on parent.id = leaf.parent_id
        {where}
        """,
        params,
    ).fetchone()
    pending_condition = " and project_id = ?" if project_id is not None else ""
    pending_params = (project_id,) if project_id is not None else ()
    pending_count = get_db().execute(
        f"""
        select count(*) from ledger_pending_items
        where status = '待补录'{pending_condition}
        """,
        pending_params,
    ).fetchone()[0]
    expense = float(row["expense"])
    reduction = float(row["expense_reduction"])
    return {
        "expense": expense,
        "expense_reduction": reduction,
        "net_expense": expense - reduction,
        "income": float(row["income"]),
        "fund_transfer": float(row["fund_transfer"]),
        "unsettled": float(row["unsettled"]),
        "entry_count": int(row["entry_count"]),
        "review_count": int(row["review_count"] or 0),
        "pending_count": int(pending_count),
    }


def create_ledger_pending_item(data: dict[str, Any]) -> int:
    category = _get_leaf_category(int(data["suggested_category_id"]))
    db = get_db()
    cursor = db.execute(
        """
        insert into ledger_pending_items (
          project_id, item_date, summary, suggested_category_id, handler_name,
          payment_notes, source_filename, source_sheet, source_row, issue_type
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(data["project_id"]),
            _validated_date(data.get("item_date"), "发生日期", required=True),
            _required_text(data.get("summary"), "事项摘要", max_length=500),
            int(category["id"]),
            str(data.get("handler_name") or ""),
            str(data.get("payment_notes") or ""),
            _required_text(data.get("source_filename"), "来源文件"),
            _required_text(data.get("source_sheet"), "来源工作表"),
            int(data["source_row"]),
            _required_text(data.get("issue_type"), "待确认问题"),
        ),
    )
    db.commit()
    return int(cursor.lastrowid)


def get_ledger_pending_item(item_id: int):
    return get_db().execute(
        "select * from ledger_pending_items where id = ?", (item_id,)
    ).fetchone()


def _ledger_pending_filter_clause(
    project_id: int | None = None, status: str | None = None
) -> tuple[str, list[Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    if project_id is not None:
        conditions.append("items.project_id = ?")
        params.append(project_id)
    if status:
        conditions.append("items.status = ?")
        params.append(status)
    where = "where " + " and ".join(conditions) if conditions else ""
    return where, params


def count_ledger_pending_items(
    project_id: int | None = None, status: str | None = None
) -> int:
    where, params = _ledger_pending_filter_clause(project_id, status)
    return int(get_db().execute(
        f"select count(*) from ledger_pending_items items {where}",
        params,
    ).fetchone()[0])


def list_ledger_pending_items(
    project_id: int | None = None,
    status: str | None = None,
    *,
    limit: int | None = None,
    offset: int = 0,
):
    where, params = _ledger_pending_filter_clause(project_id, status)
    pagination_sql = ""
    if limit is not None:
        pagination_sql = " limit ?"
        params.append(limit)
    if offset:
        pagination_sql += " offset ?"
        params.append(offset)
    return get_db().execute(
        f"""
        select items.*, projects.name as project_name,
               categories.name as suggested_category_name,
               categories.transaction_scope as suggested_transaction_scope,
               parents.name as suggested_primary_name
        from ledger_pending_items items
        join projects on projects.id = items.project_id
        left join expense_categories categories on categories.id = items.suggested_category_id
        left join expense_categories parents on parents.id = categories.parent_id
        {where}
        order by items.item_date, items.id
        {pagination_sql}
        """,
        params,
    ).fetchall()


def convert_ledger_pending_item(
    item_id: int,
    *,
    amount: Any,
    category_id: int,
    transaction_type: str,
    payment_status: str,
    actor_admin_id: int | None,
) -> int:
    db = get_db()
    item = db.execute(
        "select * from ledger_pending_items where id = ?", (item_id,)
    ).fetchone()
    if item is None:
        raise ValueError("待补录事项不存在")
    if item["status"] != "待补录":
        raise ValueError("该待补录事项已经转换或忽略")
    source_record_id = (
        f"PENDING:{item['project_id']}:{item['source_filename']}:"
        f"{item['source_sheet']}:{item['source_row']}"
    )
    try:
        voucher_id = _insert_voucher(db, {
            "project_id": item["project_id"],
            "voucher_date": item["item_date"],
            "transaction_type": transaction_type,
            "category_id": category_id,
            "amount": amount,
            "notes": item["summary"],
            "handler_name": item["handler_name"],
            "payment_status": payment_status,
            "payment_notes": item["payment_notes"],
            "source_record_id": source_record_id,
            "source_filename": item["source_filename"],
            "source_sheet": item["source_sheet"],
            "source_row": item["source_row"],
            "original_notes": item["summary"],
        })
        cursor = db.execute(
            """
            update ledger_pending_items
            set status = '已转正式明细', voucher_id = ?
            where id = ? and status = '待补录'
            """,
            (voucher_id, item_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("该待补录事项已经转换或忽略")
        _insert_audit(
            db,
            actor_admin_id=actor_admin_id,
            action="convert",
            entity_type="ledger_pending_item",
            entity_id=item_id,
            details={"voucher_id": voucher_id},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return voucher_id


def ignore_ledger_pending_item(
    item_id: int, *, actor_admin_id: int | None
) -> None:
    db = get_db()
    item = db.execute(
        "select status from ledger_pending_items where id = ?", (item_id,)
    ).fetchone()
    if item is None:
        raise ValueError("待补录事项不存在")
    if item["status"] != "待补录":
        raise ValueError("只有待补录事项可以忽略")
    try:
        cursor = db.execute(
            """
            update ledger_pending_items set status = '已忽略'
            where id = ? and status = '待补录'
            """,
            (item_id,),
        )
        if cursor.rowcount != 1:
            raise ValueError("只有待补录事项可以忽略")
        _insert_audit(
            db,
            actor_admin_id=actor_admin_id,
            action="ignore",
            entity_type="ledger_pending_item",
            entity_id=item_id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def delete_expense_category(category_id: int) -> None:
    db = get_db()
    category = db.execute(
        "select * from expense_categories where id = ?", (category_id,)
    ).fetchone()
    if category is None:
        raise ValueError("分类不存在")
    children = db.execute(
        "select count(*) from expense_categories where parent_id = ?", (category_id,)
    ).fetchone()[0]
    references = db.execute(
        "select count(*) from vouchers where category_id = ?", (category_id,)
    ).fetchone()[0]
    pending_references = db.execute(
        "select count(*) from ledger_pending_items where suggested_category_id = ?",
        (category_id,),
    ).fetchone()[0]
    if children:
        raise ValueError("一级分类仍有二级分类，不能删除")
    if references:
        raise ValueError("分类已被财务明细使用，不能删除")
    if pending_references:
        raise ValueError("分类已被待补录事项使用，不能删除")
    db.execute("delete from expense_categories where id = ?", (category_id,))
    db.commit()


def migrate_expense_category(
    source_id: int, target_id: int, *, actor_admin_id: int | None
) -> None:
    db = get_db()
    source = _get_leaf_category(source_id)
    target = _get_leaf_category(target_id)
    if source_id == target_id:
        raise ValueError("迁移目标不能与原分类相同")
    if source["transaction_scope"] != target["transaction_scope"]:
        raise ValueError("只能迁移到同一收支范围的分类")
    db.execute(
        "update vouchers set category_id = ?, voucher_type = ? where category_id = ?",
        (target_id, target["name"], source_id),
    )
    db.execute(
        """
        update ledger_pending_items set suggested_category_id = ?
        where suggested_category_id = ? and status = '待补录'
        """,
        (target_id, source_id),
    )
    db.execute(
        "update expense_categories set is_active = 0 where id = ?", (source_id,)
    )
    _insert_audit(
        db,
        actor_admin_id=actor_admin_id,
        action="migrate",
        entity_type="expense_category",
        entity_id=source_id,
        details={"target_id": target_id},
    )
    db.commit()


def list_people():
    return get_db().execute("select * from people order by created_at desc").fetchall()


def get_person(person_id: int):
    return get_db().execute("select * from people where id = ?", (person_id,)).fetchone()


def create_person(data: dict[str, Any]) -> int:
    is_att = int(data.get("is_attendance", 1))
    name = _required_text(data.get("name"), "姓名", max_length=80)
    id_number = _validated_id_number(data.get("id_number"))
    phone = _validated_phone(data.get("phone"))
    birth_date = _validated_date(data.get("birth_date"), "出生日期")
    entry_date = _validated_date(data.get("entry_date"), "入职日期")
    salary_rate = float(data.get("salary_rate", 0.0))
    if not math.isfinite(salary_rate) or salary_rate < 0:
        raise ValueError("薪资标准必须为不小于 0 的数字")
    cursor = get_db().execute(
        """
        insert into people
          (name, id_number, id_card_path, gender, birth_date, age, phone, address, job_type,
           bank_card, bank_name, entry_date, notes, review_status, is_attendance,
           salary_type, salary_rate)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            id_number,
            data.get("id_card_path", ""),
            data.get("gender", ""),
            birth_date,
            data.get("age"),
            phone,
            data.get("address", ""),
            data.get("job_type", ""),
            data.get("bank_card", ""),
            data.get("bank_name", ""),
            entry_date,
            data.get("notes", ""),
            data.get("review_status", "已确认"),
            is_att,
            data.get("salary_type", "日薪"),
            salary_rate,
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)


def list_qualifications():
    return get_db().execute(
        """
        select qualifications.*, companies.name as company_name
        from qualifications
        join companies on companies.id = qualifications.company_id
        order by companies.is_main desc, companies.name, qualifications.expiry_date
        """
    ).fetchall()


def create_qualification(data: dict[str, Any]) -> int:
    cursor = get_db().execute(
        """
        insert into qualifications
          (company_id, name, certificate_no, issue_date, expiry_date,
           is_long_term, attachment_path, notes)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["company_id"],
            data["name"],
            data["certificate_no"],
            data.get("issue_date", ""),
            data.get("expiry_date", ""),
            int(data.get("is_long_term", 0)),
            data.get("attachment_path", ""),
            data.get("notes", ""),
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)


def create_batch_item(data: dict[str, Any]) -> int:
    cursor = get_db().execute(
        """
        insert into batch_items
          (item_type, source_filename, stored_path, status, recognized_json, confidence)
        values (?, ?, ?, ?, ?, ?)
        """,
        (
            data["item_type"],
            data["source_filename"],
            data.get("stored_path", ""),
            data.get("status", "待确认"),
            data.get("recognized_json", "{}"),
            data.get("confidence"),
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)


def list_batch_items(item_type: str | None = None):
    if item_type:
        return get_db().execute(
            "select * from batch_items where item_type = ? order by created_at desc",
            (item_type,),
        ).fetchall()
    return get_db().execute("select * from batch_items order by created_at desc").fetchall()


def get_batch_item(item_id: int):
    return get_db().execute(
        "select * from batch_items where id = ?",
        (item_id,),
    ).fetchone()


def delete_batch_item(item_id: int) -> None:
    get_db().execute("delete from batch_items where id = ?", (item_id,))
    get_db().commit()


def update_batch_item_status(item_id: int, status: str) -> None:
    get_db().execute(
        "update batch_items set status = ? where id = ?",
        (status, item_id),
    )
    get_db().commit()


def update_batch_item_recognition(
    item_id: int,
    *,
    status: str,
    recognized_json: str,
    confidence: float | None,
) -> None:
    get_db().execute(
        """
        update batch_items
        set status = ?, recognized_json = ?, confidence = ?
        where id = ?
        """,
        (status, recognized_json, confidence, item_id),
    )
    get_db().commit()


def update_project(project_id: int, data: dict[str, Any]) -> None:
    name = _required_text(data.get("name"), "项目名称")
    status = str(data.get("status") or "进行中")
    if status not in PROJECT_STATUSES:
        raise ValueError("项目状态无效")
    start_date = _validated_date(data.get("start_date"), "开工日期")
    end_date = _validated_date(data.get("end_date"), "完工日期")
    if start_date and end_date and end_date < start_date:
        raise ValueError("完工日期不能早于开工日期")
    get_db().execute(
        """
        update projects
        set name = ?, status = ?, owner = ?, start_date = ?, end_date = ?, notes = ?
        where id = ?
        """,
        (
            name,
            status,
            data.get("owner", ""),
            start_date,
            end_date,
            data.get("notes", ""),
            project_id,
        ),
    )
    get_db().commit()


def update_voucher(voucher_id: int, data: dict[str, Any]) -> None:
    db = get_db()
    existing = db.execute("select * from vouchers where id = ?", (voucher_id,)).fetchone()
    if existing is None:
        raise ValueError("凭证不存在")
    if existing["is_void"]:
        raise ValueError("已作废凭证不能修改")
    if data.get("category_id"):
        amount = normalize_amount(data["amount"])
        voucher_date = _validated_date(data.get("voucher_date"), "凭证日期", required=True)
        transaction_type = _validated_choice(
            data.get("transaction_type", existing["transaction_type"]),
            "收支类型",
            TRANSACTION_TYPES,
        )
        category = _get_leaf_category(int(data["category_id"]))
        expected_scope = "支出" if transaction_type in {"支出", "冲减支出"} else transaction_type
        if category["transaction_scope"] != expected_scope:
            raise ValueError("分类与收支类型不匹配")
        payment_status = _validated_choice(
            data.get("payment_status", existing["payment_status"]),
            "付款状态",
            PAYMENT_STATUSES,
        )
        review_status = _validated_choice(
            data.get("review_status", existing["review_status"]),
            "复核状态",
            REVIEW_STATUSES,
        )
        db.execute(
            """
            update vouchers
            set project_id = ?, voucher_date = ?, voucher_type = ?, amount = ?, notes = ?,
                transaction_type = ?, category_id = ?, handler_name = ?, payment_status = ?,
                payment_date = ?, payment_notes = ?, review_status = ?
            where id = ?
            """,
            (
                int(data["project_id"]), voucher_date, category["name"], amount,
                data.get("notes", ""),
                transaction_type, category["id"],
                data.get("handler_name", ""), payment_status,
                _validated_date(data.get("payment_date"), "付款日期"),
                data.get("payment_notes", ""), review_status, voucher_id,
            ),
        )
        details = {"amount": amount, "voucher_date": voucher_date, "type": transaction_type}
    else:
        amount = normalize_amount(data["amount"])
        voucher_date = _validated_date(data.get("voucher_date"), "凭证日期", required=True)
        voucher_type = _required_text(data.get("voucher_type"), "凭证类型")
        db.execute(
            """
            update vouchers
            set voucher_date = ?, voucher_type = ?, amount = ?, notes = ?, entry_user = ?
            where id = ?
            """,
            (voucher_date, voucher_type, amount, data.get("notes", ""), data.get("entry_user", ""), voucher_id),
        )
        details = {"amount": amount, "voucher_date": voucher_date, "type": voucher_type}
    _insert_audit(
        db,
        actor_admin_id=data.get("actor_admin_id"),
        action="update",
        entity_type="voucher",
        entity_id=voucher_id,
        details=details,
    )
    db.commit()


def void_voucher(voucher_id: int, reason: Any, *, actor_admin_id: int | None) -> None:
    reason_text = _required_text(reason, "作废原因", max_length=500)
    db = get_db()
    voucher = db.execute("select * from vouchers where id = ?", (voucher_id,)).fetchone()
    if voucher is None:
        raise ValueError("凭证不存在")
    if voucher["is_void"]:
        raise ValueError("凭证已经作废")
    db.execute(
        """
        update vouchers
        set is_void = 1, void_reason = ?, voided_at = current_timestamp,
            voided_by_admin_id = ?
        where id = ?
        """,
        (reason_text, actor_admin_id, voucher_id),
    )
    _insert_audit(
        db,
        actor_admin_id=actor_admin_id,
        action="void",
        entity_type="voucher",
        entity_id=voucher_id,
        details={"reason": reason_text, "amount": voucher["amount"]},
    )
    db.commit()


def update_person(person_id: int, data: dict[str, Any]) -> None:
    name = _required_text(data.get("name"), "姓名", max_length=80)
    id_number = _validated_id_number(data.get("id_number"))
    phone = _validated_phone(data.get("phone"))
    birth_date = _validated_date(data.get("birth_date"), "出生日期")
    entry_date = _validated_date(data.get("entry_date"), "入职日期")
    salary_rate = float(data.get("salary_rate", 0.0))
    if not math.isfinite(salary_rate) or salary_rate < 0:
        raise ValueError("薪资标准必须为不小于 0 的数字")
    set_clause = """
        name = ?, id_number = ?, gender = ?, birth_date = ?, age = ?, phone = ?,
        address = ?, job_type = ?, bank_card = ?, bank_name = ?, entry_date = ?, notes = ?,
        is_attendance = ?, salary_type = ?, salary_rate = ?
    """
    params: list[Any] = [
        name,
        id_number,
        data.get("gender", ""),
        birth_date,
        data.get("age"),
        phone,
        data.get("address", ""),
        data.get("job_type", ""),
        data.get("bank_card", ""),
        data.get("bank_name", ""),
        entry_date,
        data.get("notes", ""),
        int(data.get("is_attendance", 1)),
        data.get("salary_type", "日薪"),
        salary_rate,
    ]

    if data.get("id_card_path"):
        set_clause += ", id_card_path = ?"
        params.append(data["id_card_path"])

    params.append(person_id)
    get_db().execute(
        f"update people set {set_clause} where id = ?",
        tuple(params),
    )
    get_db().commit()


def update_qualification(qualification_id: int, data: dict[str, Any]) -> None:
    set_clause = """
        company_id = ?, name = ?, certificate_no = ?, issue_date = ?, expiry_date = ?,
        is_long_term = ?, notes = ?
    """
    params = [
        data["company_id"],
        data["name"],
        data["certificate_no"],
        data.get("issue_date", ""),
        data.get("expiry_date", ""),
        int(data.get("is_long_term", 0)),
        data.get("notes", ""),
    ]
    
    if "attachment_path" in data and data["attachment_path"]:
        set_clause += ", attachment_path = ?"
        params.append(data["attachment_path"])
        
    params.append(qualification_id)
    
    get_db().execute(
        f"update qualifications set {set_clause} where id = ?",
        tuple(params)
    )
    get_db().commit()


def delete_qualification(qualification_id: int) -> None:
    get_db().execute("delete from qualifications where id = ?", (qualification_id,))
    get_db().commit()


def delete_person(person_id: int) -> None:
    db = get_db()
    related = db.execute(
        """
        select
          (select count(*) from salary_payments where person_id = ?) as payments,
          (select count(*) from salary_sheets where person_id = ?) as sheets
        """,
        (person_id, person_id),
    ).fetchone()
    if related["payments"] or related["sheets"]:
        raise ValueError("人员存在工资流水或结算记录，不能删除历史档案")
    db.execute("delete from people where id = ?", (person_id,))
    db.commit()


def delete_project(project_id: int, *, actor_admin_id: int | None = None) -> None:
    db = get_db()
    project = db.execute("select * from projects where id = ?", (project_id,)).fetchone()
    if project is None:
        raise ValueError("项目不存在")
    related = db.execute(
        """
        select
            (select count(*) from vouchers where project_id = ?) as voucher_count,
            (select count(*) from contracts where project_id = ?) as contract_count
        """,
        (project_id, project_id),
    ).fetchone()
    if related["voucher_count"] or related["contract_count"]:
        raise ValueError("项目仍有关联凭证或合同，不能删除；请保留项目作为历史台账")
    db.execute("delete from projects where id = ?", (project_id,))
    _insert_audit(
        db,
        actor_admin_id=actor_admin_id,
        action="delete",
        entity_type="project",
        entity_id=project_id,
        details={"name": project["name"]},
    )
    db.commit()


def list_attendance_by_month(year_month: str):
    return get_db().execute(
        "select * from attendance where work_date like ? order by work_date, person_id",
        (f"{year_month}%",),
    ).fetchall()


def save_attendance(person_id: int, work_date: str, shift_type: str | None) -> None:
    db = get_db()
    if not shift_type:
        db.execute(
            "delete from attendance where person_id = ? and work_date = ?",
            (person_id, work_date),
        )
    else:
        db.execute(
            """
            insert into attendance (person_id, work_date, shift_type)
            values (?, ?, ?)
            on conflict(person_id, work_date) do update set shift_type = excluded.shift_type
            """,
            (person_id, work_date, shift_type),
        )
    db.commit()


def list_attendance_people():
    return get_db().execute(
        "select * from people where is_attendance = 1 order by created_at desc"
    ).fetchall()


def update_people_attendance_status(status_map: dict[int, int]) -> None:
    db = get_db()
    for person_id, is_att in status_map.items():
        db.execute(
            "update people set is_attendance = ? where id = ?",
            (is_att, person_id),
        )
    db.commit()


def list_contracts(project_id: int | None = None, contract_type: str | None = None, query: str | None = None):
    db = get_db()
    params: list[Any] = []
    where_clauses: list[str] = []
    
    if project_id:
        where_clauses.append("contracts.project_id = ?")
        params.append(project_id)
    if contract_type:
        where_clauses.append("contracts.contract_type = ?")
        params.append(contract_type)
    if query:
        where_clauses.append("(contracts.name like ? or contracts.notes like ?)")
        params.append(f"%{query}%")
        params.append(f"%{query}%")
        
    where = f"where {' and '.join(where_clauses)}" if where_clauses else ""
    
    return db.execute(
        f"""
        select contracts.*, projects.name as project_name
        from contracts
        join projects on projects.id = contracts.project_id
        {where}
        order by contracts.created_at desc, contracts.id desc
        """,
        params,
    ).fetchall()


def get_contract(contract_id: int):
    return get_db().execute(
        """
        select contracts.*, projects.name as project_name
        from contracts
        join projects on projects.id = contracts.project_id
        where contracts.id = ?
        """,
        (contract_id,),
    ).fetchone()


def create_contract(data: dict[str, Any]) -> int:
    cursor = get_db().execute(
        """
        insert into contracts (project_id, name, contract_type, attachment_path, notes, person_id, status, template_name)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["project_id"],
            data["name"],
            data.get("contract_type", "其它"),
            data.get("attachment_path", ""),
            data.get("notes", ""),
            data.get("person_id"),
            data.get("status", "待签署"),
            data.get("template_name", ""),
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)


def update_contract(contract_id: int, data: dict[str, Any]) -> None:
    set_clause = """
        project_id = ?, name = ?, contract_type = ?, notes = ?
    """
    params = [
        data["project_id"],
        data["name"],
        data.get("contract_type", "其它"),
        data.get("notes", ""),
    ]
    
    if "attachment_path" in data and data["attachment_path"]:
        set_clause += ", attachment_path = ?"
        params.append(data["attachment_path"])

    if "status" in data and data["status"]:
        set_clause += ", status = ?"
        params.append(data["status"])
        
    params.append(contract_id)
    
    get_db().execute(
        f"update contracts set {set_clause} where id = ?",
        tuple(params)
    )
    get_db().commit()


def delete_contract(contract_id: int) -> None:
    get_db().execute("delete from contracts where id = ?", (contract_id,))
    get_db().commit()


def list_salary_payments(person_id: int | None = None, month: str | None = None) -> list[dict[str, Any]]:
    db = get_db()
    query = """
        select salary_payments.*, people.name as person_name, people.job_type
        from salary_payments
        join people on people.id = salary_payments.person_id
    """
    where_clauses = []
    params = []
    
    if person_id is not None:
        where_clauses.append("salary_payments.person_id = ?")
        params.append(person_id)
        
    if month is not None:
        where_clauses.append("salary_payments.payment_date like ?")
        params.append(f"{month}-%")
        
    if where_clauses:
        query += " where " + " and ".join(where_clauses)
        
    query += " order by salary_payments.payment_date desc, salary_payments.created_at desc"
    return db.execute(query, tuple(params)).fetchall()


def create_salary_payment(data: dict[str, Any]) -> int:
    db = get_db()
    payment_date = _validated_date(data.get("payment_date"), "付款日期", required=True)
    payment_type = str(data.get("payment_type") or "")
    if payment_type not in {"预支工资", "工资发放"}:
        raise ValueError("收付款类别无效")
    amount = normalize_amount(data.get("amount"))
    cursor = db.execute(
        """
        insert into salary_payments (person_id, payment_date, payment_type, amount, notes)
        values (?, ?, ?, ?, ?)
        """,
        (
            data["person_id"],
            payment_date,
            payment_type,
            amount,
            data.get("notes", ""),
        ),
    )
    payment_id = int(cursor.lastrowid)
    _insert_audit(
        db,
        actor_admin_id=data.get("actor_admin_id"),
        action="create",
        entity_type="salary_payment",
        entity_id=payment_id,
        details={"person_id": data["person_id"], "amount": amount, "type": payment_type},
    )
    db.commit()
    return payment_id


def delete_salary_payment(payment_id: int) -> None:
    db = get_db()
    db.execute("delete from salary_payments where id = ?", (payment_id,))
    db.commit()


def get_salary_summary_by_month(month: str) -> list[dict[str, Any]]:
    import calendar
    
    try:
        year, month_num = map(int, month.split("-"))
        _, days_in_month = calendar.monthrange(year, month_num)
    except Exception:
        days_in_month = 30
        
    db = get_db()
    people = db.execute(
        "select id, name, job_type, salary_type, salary_rate from people where is_attendance = 1 order by created_at desc"
    ).fetchall()
    
    attendance_records = db.execute(
        "select person_id, shift_type from attendance where work_date like ?",
        (f"{month}-%",)
    ).fetchall()
    
    att_map = {}
    for r in attendance_records:
        pid = r["person_id"]
        shift = r["shift_type"]
        if pid not in att_map:
            att_map[pid] = {"day": 0, "night": 0, "leave": 0}
        if shift in ("白班", "夜班", "上班"):
            att_map[pid]["day"] += 1
        elif shift == "请假":
            att_map[pid]["leave"] += 1
            
    payments = db.execute(
        "select person_id, payment_type, amount from salary_payments where payment_date like ?",
        (f"{month}-%",)
    ).fetchall()
    
    pay_map = {}
    for p in payments:
        pid = p["person_id"]
        ptype = p["payment_type"]
        amt = p["amount"]
        if pid not in pay_map:
            pay_map[pid] = {"advance": 0.0, "payout": 0.0}
        if ptype == "预支工资":
            pay_map[pid]["advance"] += amt
        elif ptype == "工资发放":
            pay_map[pid]["payout"] += amt
            
    summary_list = []
    for p in people:
        pid = p["id"]
        att = att_map.get(pid, {"day": 0, "night": 0, "leave": 0})
        pay = pay_map.get(pid, {"advance": 0.0, "payout": 0.0})
        
        sal_type = p["salary_type"]
        sal_rate = p["salary_rate"]
        
        work_days = att["day"] + att["night"]
        leave_days = att["leave"]
        
        earnings = 0.0
        if sal_type == "日薪":
            earnings = work_days * sal_rate
        elif sal_type == "月薪":
            if days_in_month > 0:
                deduction = leave_days * (sal_rate / days_in_month)
                earnings = max(0.0, sal_rate - deduction)
            else:
                earnings = sal_rate
        elif sal_type == "年薪":
            earnings = sal_rate / 12.0
        else:
            earnings = 0.0
            
        balance = earnings - pay["advance"] - pay["payout"]
        
        summary_list.append({
            "person_id": pid,
            "name": p["name"],
            "job_type": p["job_type"],
            "salary_type": sal_type,
            "salary_rate": sal_rate,
            "day": att["day"],
            "night": att["night"],
            "leave": leave_days,
            "work_days": work_days,
            "earnings": round(earnings, 2),
            "advance": round(pay["advance"], 2),
            "payout": round(pay["payout"], 2),
            "balance": round(balance, 2)
        })
        
    return summary_list


def list_salary_sheets_by_person(person_id: int) -> list[dict[str, Any]]:
    db = get_db()
    rows = db.execute(
        """
        select *
        from salary_sheets
        where person_id = ?
        order by settle_month asc, id asc
        """,
        (person_id,),
    ).fetchall()
    
    results = []
    current_balance = 0.0
    for row in rows:
        item = dict(row)
        current_balance += item["earnings"] - item["paid_amount"]
        item["balance"] = round(current_balance, 2)
        
        month_str = item["settle_month"]
        try:
            if "-" in month_str:
                y, m = month_str.split("-")
                item["formatted_month"] = f"{int(y)}年{int(m)}月"
            else:
                item["formatted_month"] = month_str
        except Exception:
            item["formatted_month"] = month_str
            
        results.append(item)
    return results


def create_salary_sheet_item(data: dict[str, Any]) -> int:
    db = get_db()
    settle_month = _validated_month(data.get("settle_month"), "结算月份")
    numeric_fields = {
        "should_work_days": float(data.get("should_work_days", 30.0)),
        "actual_work_days": float(data.get("actual_work_days", 30.0)),
        "salary_rate": float(data.get("salary_rate", 0.0)),
        "earnings": float(data.get("earnings", 0.0)),
        "paid_amount": float(data.get("paid_amount", 0.0)),
    }
    if any(not math.isfinite(value) or value < 0 for value in numeric_fields.values()):
        raise ValueError("工资天数和金额必须是不小于 0 的有限数字")
    cursor = db.execute(
        """
        insert into salary_sheets 
          (person_id, settle_month, should_work_days, actual_work_days, salary_rate, earnings, paid_amount, notes)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["person_id"],
            settle_month,
            numeric_fields["should_work_days"],
            numeric_fields["actual_work_days"],
            numeric_fields["salary_rate"],
            numeric_fields["earnings"],
            numeric_fields["paid_amount"],
            data.get("notes", ""),
        ),
    )
    sheet_id = int(cursor.lastrowid)
    _insert_audit(
        db,
        actor_admin_id=data.get("actor_admin_id"),
        action="create",
        entity_type="salary_sheet",
        entity_id=sheet_id,
        details={"person_id": data["person_id"], "month": settle_month},
    )
    db.commit()
    return sheet_id


def delete_salary_sheet_item(item_id: int) -> None:
    db = get_db()
    db.execute("delete from salary_sheets where id = ?", (item_id,))
    db.commit()
