from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from flask import current_app
from flask import g


DEFAULT_EXPENSE_CATEGORIES = [
    "员工报销",
    "转账凭证",
    "材料费用",
    "油费",
    "电费",
    "人工工资",
    "其它",
]


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database = Path(current_app.config["DATABASE"])
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys = on")
        g.db = connection
    return g.db


def close_db(_: Any = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app) -> None:
    app.teardown_appcontext(close_db)


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        create table if not exists companies (
            id integer primary key autoincrement,
            name text not null unique,
            credit_code text not null default '',
            legal_person text not null default '',
            phone text not null default '',
            notes text not null default '',
            is_main integer not null default 0,
            created_at text not null default current_timestamp
        );

        create table if not exists projects (
            id integer primary key autoincrement,
            company_id integer not null references companies(id),
            name text not null,
            status text not null default '进行中',
            owner text not null default '',
            start_date text not null default '',
            end_date text not null default '',
            notes text not null default '',
            created_at text not null default current_timestamp
        );

        create table if not exists vouchers (
            id integer primary key autoincrement,
            project_id integer not null references projects(id),
            voucher_date text not null,
            voucher_type text not null,
            amount real not null check(amount > 0),
            notes text not null default '',
            attachment_path text not null default '',
            entry_user text not null default '',
            created_at text not null default current_timestamp
        );

        create table if not exists expense_categories (
            id integer primary key autoincrement,
            name text not null unique,
            sort_order integer not null default 0,
            is_active integer not null default 1,
            created_at text not null default current_timestamp
        );

        create table if not exists people (
            id integer primary key autoincrement,
            name text not null,
            id_number text not null unique,
            id_card_path text not null default '',
            gender text not null default '',
            birth_date text not null default '',
            age integer,
            phone text not null default '',
            address text not null default '',
            job_type text not null default '',
            bank_card text not null default '',
            bank_name text not null default '',
            entry_date text not null default '',
            notes text not null default '',
            review_status text not null default '已确认',
            is_attendance integer not null default 1,
            created_at text not null default current_timestamp
        );

        create table if not exists qualifications (
            id integer primary key autoincrement,
            company_id integer not null references companies(id),
            name text not null,
            certificate_no text not null,
            issue_date text not null default '',
            expiry_date text not null default '',
            is_long_term integer not null default 0,
            attachment_path text not null default '',
            notes text not null default '',
            created_at text not null default current_timestamp
        );

        create table if not exists batch_items (
            id integer primary key autoincrement,
            item_type text not null,
            source_filename text not null,
            stored_path text not null default '',
            status text not null default '待确认',
            recognized_json text not null default '{}',
            confidence real,
            created_at text not null default current_timestamp
        );

        create table if not exists attendance (
            id integer primary key autoincrement,
            person_id integer not null references people(id) on delete cascade,
            work_date text not null,
            shift_type text not null,
            notes text not null default '',
            created_at text not null default current_timestamp,
            unique(person_id, work_date)
        );
        """
    )
    people_columns = {
        row["name"] for row in db.execute("pragma table_info(people)").fetchall()
    }
    if "id_card_path" not in people_columns:
        db.execute("alter table people add column id_card_path text not null default ''")
    if "is_attendance" not in people_columns:
        db.execute("alter table people add column is_attendance integer not null default 1")

    db.execute(
        """
        insert into companies (name, is_main)
        select '主公司', 1
        where not exists (select 1 from companies where is_main = 1)
        """
    )
    category_count = db.execute("select count(*) from expense_categories").fetchone()[0]
    if category_count == 0:
        db.executemany(
            """
            insert into expense_categories (name, sort_order, is_active)
            values (?, ?, 1)
            """,
            [(name, index * 10) for index, name in enumerate(DEFAULT_EXPENSE_CATEGORIES, start=1)],
        )
    db.execute(
        """
        update batch_items
        set status = '待确认'
        where status not in ('待确认', '已识别', '已确认')
        """
    )
    
    # 自动生成精美施工人员和考勤测试数据 (用于演示及易用性验证)
    if not current_app.config.get("TESTING"):
        people_count = db.execute("select count(*) from people").fetchone()[0]
        if people_count == 0:
            test_people = [
                ("刘思伟", "410101199001010001", "男", 36, "13800138001", "普工", "6222021702019988771", "中国工商银行", "2026-05-10"),
                ("李刘成", "410101199001010002", "男", 34, "13900139002", "普工", "6228481234567890123", "中国农业银行", "2026-05-12"),
                ("王成", "410101199001010003", "男", 31, "13600136004", "水泥工", "6217001234567890456", "中国建设银行", "2026-05-15"),
                ("雷威", "410101199001010004", "男", 41, "13500135005", "架子工", "6222601234567890789", "交通银行", "2026-05-18"),
                ("李军", "410101199001010005", "男", 38, "13700137003", "水泥工", "6230521234567890987", "中国邮政储蓄银行", "2026-05-20"),
                ("刘新田", "410101199001010006", "男", 29, "13800138002", "普工", "6222021702019988772", "中国工商银行", "2026-05-22"),
                ("李和羊", "410101199001010007", "男", 33, "13900139003", "普工", "6228481234567890124", "中国农业银行", "2026-05-23"),
                ("李金洲", "410101199001010008", "男", 35, "13600136005", "架子工", "6217001234567890457", "中国建设银行", "2026-05-24"),
                ("王建民", "410101199001010009", "男", 40, "13500135006", "安全员", "6222601234567890790", "交通银行", "2026-05-25"),
                ("黄林刚", "410101199001010010", "男", 37, "13700137004", "普工", "6230521234567890988", "中国邮政储蓄银行", "2026-05-26"),
                ("方强", "410101199001010011", "男", 30, "13800138003", "水泥工", "6222021702019988773", "中国工商银行", "2026-05-27"),
                ("宁守付", "410101199001010012", "男", 42, "13900139004", "架子工", "6228481234567890125", "中国农业银行", "2026-05-28"),
                ("赵全", "410101199001010013", "男", 28, "13600136006", "资料员", "6217001234567890458", "中国建设银行", "2026-05-29"),
                ("王军喜", "410101199001010014", "男", 45, "13500135007", "普工", "6222601234567890791", "交通银行", "2026-05-30"),
                ("李勇", "410101199001010015", "男", 32, "13700137005", "安全员", "6230521234567890989", "中国邮政储蓄银行", "2026-06-01"),
                ("袁爱贵", "410101199001010016", "男", 39, "13800138004", "普工", "6222021702019988774", "中国工商银行", "2026-06-01"),
                ("李光", "410101199001010017", "男", 34, "13900139005", "普工", "6228481234567890126", "中国农业银行", "2026-06-01"),
            ]
            for p in test_people:
                cursor = db.execute(
                    """
                    insert into people (name, id_number, gender, age, phone, job_type, bank_card, bank_name, entry_date, review_status)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, '已确认')
                    """,
                    p,
                )
                person_id = cursor.lastrowid
                
                attendance_dates = []
                if p[0] == "李光":
                    # 李光在 2026-05 的 27, 28, 29, 31 号请假
                    attendance_dates.append(("2026-05-27", "请假"))
                    attendance_dates.append(("2026-05-28", "请假"))
                    attendance_dates.append(("2026-05-29", "请假"))
                    attendance_dates.append(("2026-05-31", "请假"))
                else:
                    name_hash = sum(ord(c) for c in p[0])
                    if name_hash % 3 == 0:
                        for d in range(1, 15):
                            if d % 5 == 0:
                                attendance_dates.append((f"2026-06-{d:02d}", "请假"))
                            elif d % 2 == 0:
                                attendance_dates.append((f"2026-06-{d:02d}", "白班"))
                            else:
                                attendance_dates.append((f"2026-06-{d:02d}", "夜班"))
                    elif name_hash % 3 == 1:
                        for d in range(1, 10):
                            attendance_dates.append((f"2026-06-{d:02d}", "白班"))
                        for d in range(15, 20):
                            attendance_dates.append((f"2026-06-{d:02d}", "请假"))
                    else:
                        for d in range(5, 15):
                            attendance_dates.append((f"2026-06-{d:02d}", "夜班"))
                
                db.executemany(
                    "insert into attendance (person_id, work_date, shift_type) values (?, ?, ?)",
                    [(person_id, date, shift) for date, shift in attendance_dates],
                )
    db.commit()
