from __future__ import annotations

from typing import Any

from .db import get_db


def normalize_amount(value: Any) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("金额必须是数字") from exc
    if amount <= 0:
        raise ValueError("金额必须大于 0")
    return amount


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


def list_projects():
    return get_db().execute(
        """
        select projects.*, companies.name as company_name
        from projects
        join companies on companies.id = projects.company_id
        order by projects.created_at desc
        """
    ).fetchall()


def create_project(data: dict[str, Any]) -> int:
    cursor = get_db().execute(
        """
        insert into projects (company_id, name, status, owner, start_date, end_date, notes)
        values (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["company_id"],
            data["name"],
            data.get("status", "进行中"),
            data.get("owner", ""),
            data.get("start_date", ""),
            data.get("end_date", ""),
            data.get("notes", ""),
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)


def list_vouchers(project_id: int | None = None):
    params: list[Any] = []
    where = ""
    if project_id:
        where = "where vouchers.project_id = ?"
        params.append(project_id)
    return get_db().execute(
        f"""
        select vouchers.*, projects.name as project_name
        from vouchers
        join projects on projects.id = vouchers.project_id
        {where}
        order by vouchers.voucher_date desc, vouchers.created_at desc
        """,
        params,
    ).fetchall()


def create_voucher(data: dict[str, Any]) -> int:
    amount = normalize_amount(data["amount"])
    cursor = get_db().execute(
        """
        insert into vouchers
          (project_id, voucher_date, voucher_type, amount, notes, attachment_path, entry_user)
        values (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["project_id"],
            data["voucher_date"],
            data["voucher_type"],
            amount,
            data.get("notes", ""),
            data.get("attachment_path", ""),
            data.get("entry_user", ""),
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)
