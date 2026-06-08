from __future__ import annotations

import sqlite3
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


def list_expense_categories(include_inactive: bool = False):
    where = "" if include_inactive else "where is_active = 1"
    return get_db().execute(
        f"""
        select *
        from expense_categories
        {where}
        order by sort_order, id
        """
    ).fetchall()


def list_expense_category_names(include_inactive: bool = False) -> list[str]:
    return [row["name"] for row in list_expense_categories(include_inactive=include_inactive)]


def list_voucher_type_names(project_id: int | None = None) -> list[str]:
    params: list[Any] = []
    where = ""
    if project_id:
        where = "where project_id = ?"
        params.append(project_id)
    rows = get_db().execute(
        f"""
        select distinct voucher_type
        from vouchers
        {where}
        order by voucher_type
        """,
        params,
    ).fetchall()
    return [row["voucher_type"] for row in rows]


def create_expense_category(data: dict[str, Any]) -> int:
    name = normalize_expense_category_name(data["name"])
    sort_order = normalize_sort_order(data.get("sort_order"))
    try:
        cursor = get_db().execute(
            """
            insert into expense_categories (name, sort_order, is_active)
            values (?, ?, 1)
            """,
            (name, sort_order),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("费用科目名称不能重复") from exc
    get_db().commit()
    return int(cursor.lastrowid)


def update_expense_category(category_id: int, data: dict[str, Any]) -> None:
    db = get_db()
    existing = db.execute("select * from expense_categories where id = ?", (category_id,)).fetchone()
    if existing is None:
        raise ValueError("费用科目不存在")

    name = normalize_expense_category_name(data["name"])
    sort_order = normalize_sort_order(data.get("sort_order"))
    is_active = 1 if data.get("is_active") else 0

    try:
        db.execute(
            """
            update expense_categories
            set name = ?, sort_order = ?, is_active = ?
            where id = ?
            """,
            (name, sort_order, is_active, category_id),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("费用科目名称不能重复") from exc

    if existing["name"] != name:
        db.execute(
            """
            update vouchers
            set voucher_type = ?
            where voucher_type = ?
            """,
            (name, existing["name"]),
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


def list_people():
    return get_db().execute("select * from people order by created_at desc").fetchall()


def create_person(data: dict[str, Any]) -> int:
    is_att = int(data.get("is_attendance", 1))
    cursor = get_db().execute(
        """
        insert into people
          (name, id_number, id_card_path, gender, birth_date, age, phone, address, job_type,
           bank_card, bank_name, entry_date, notes, review_status, is_attendance,
           salary_type, salary_rate)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["name"],
            data["id_number"],
            data.get("id_card_path", ""),
            data.get("gender", ""),
            data.get("birth_date", ""),
            data.get("age"),
            data.get("phone", ""),
            data.get("address", ""),
            data.get("job_type", ""),
            data.get("bank_card", ""),
            data.get("bank_name", ""),
            data.get("entry_date", ""),
            data.get("notes", ""),
            data.get("review_status", "已确认"),
            is_att,
            data.get("salary_type", "日薪"),
            float(data.get("salary_rate", 0.0)),
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
    get_db().execute(
        """
        update projects
        set name = ?, status = ?, owner = ?, start_date = ?, end_date = ?, notes = ?
        where id = ?
        """,
        (
            data["name"],
            data.get("status", "进行中"),
            data.get("owner", ""),
            data.get("start_date", ""),
            data.get("end_date", ""),
            data.get("notes", ""),
            project_id,
        ),
    )
    get_db().commit()


def update_voucher(voucher_id: int, data: dict[str, Any]) -> None:
    amount = normalize_amount(data["amount"])
    get_db().execute(
        """
        update vouchers
        set voucher_date = ?, voucher_type = ?, amount = ?, notes = ?, entry_user = ?
        where id = ?
        """,
        (
            data["voucher_date"],
            data["voucher_type"],
            amount,
            data.get("notes", ""),
            data.get("entry_user", ""),
            voucher_id,
        ),
    )
    get_db().commit()


def update_person(person_id: int, data: dict[str, Any]) -> None:
    set_clause = """
        name = ?, id_number = ?, gender = ?, birth_date = ?, age = ?, phone = ?,
        address = ?, job_type = ?, bank_card = ?, bank_name = ?, entry_date = ?, notes = ?,
        is_attendance = ?, salary_type = ?, salary_rate = ?
    """
    params: list[Any] = [
        data["name"],
        data["id_number"],
        data.get("gender", ""),
        data.get("birth_date", ""),
        data.get("age"),
        data.get("phone", ""),
        data.get("address", ""),
        data.get("job_type", ""),
        data.get("bank_card", ""),
        data.get("bank_name", ""),
        data.get("entry_date", ""),
        data.get("notes", ""),
        int(data.get("is_attendance", 1)),
        data.get("salary_type", "日薪"),
        float(data.get("salary_rate", 0.0)),
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
    get_db().execute("delete from people where id = ?", (person_id,))
    get_db().commit()


def delete_project(project_id: int) -> None:
    db = get_db()
    db.execute("delete from vouchers where project_id = ?", (project_id,))
    db.execute("delete from contracts where project_id = ?", (project_id,))
    db.execute("delete from projects where id = ?", (project_id,))
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
        insert into contracts (project_id, name, contract_type, attachment_path, notes)
        values (?, ?, ?, ?, ?)
        """,
        (
            data["project_id"],
            data["name"],
            data.get("contract_type", "其它"),
            data.get("attachment_path", ""),
            data.get("notes", ""),
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
    cursor = db.execute(
        """
        insert into salary_payments (person_id, payment_date, payment_type, amount, notes)
        values (?, ?, ?, ?, ?)
        """,
        (
            data["person_id"],
            data["payment_date"],
            data["payment_type"],
            float(data["amount"]),
            data.get("notes", ""),
        ),
    )
    db.commit()
    return int(cursor.lastrowid)


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
        if shift == "白班":
            att_map[pid]["day"] += 1
        elif shift == "夜班":
            att_map[pid]["night"] += 1
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


