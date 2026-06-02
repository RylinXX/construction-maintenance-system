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

        # 扩充项目、资质、企业与费用凭证演示数据 (用于全系统演示)
        # 1. 升级公司名称及插入关联外包企业
        db.execute("update companies set name = '河南建工第八建设集团有限公司' where is_main = 1 and name = '主公司'")
        company_exists = db.execute("select 1 from companies where name = '商丘市瑞隆土石方工程有限公司'").fetchone()
        if not company_exists:
            db.execute(
                """
                insert into companies (name, credit_code, legal_person, phone, notes, is_main)
                values ('商丘市瑞隆土石方工程有限公司', '91411402MAD31X8L9Y', '瑞德隆', '15837012345', '土石方专业分包合作商', 0)
                """
            )

        # 2. 插入精美演示项目
        project_count = db.execute("select count(*) from projects").fetchone()[0]
        if project_count == 0:
            main_company_id = db.execute("select id from companies where is_main = 1").fetchone()[0]
            db.execute(
                """
                insert into projects (company_id, name, status, owner, start_date, end_date, notes)
                values (?, '郑州地铁6号线二期机电维保工程', '进行中', '郑州地铁集团', '2026-01-01', '2026-12-31', '包含地铁站点区间内机电与管线常规维护')
                """,
                (main_company_id,)
            )
            db.execute(
                """
                insert into projects (company_id, name, status, owner, start_date, end_date, notes)
                values (?, '郑州市中原路绿化提升改造项目', '进行中', '郑州市市政管理局', '2026-03-15', '2026-08-30', '中原路主干道绿化补植与灌溉系统升级')
                """,
                (main_company_id,)
            )

        # 3. 插入精美资质数据
        qualification_count = db.execute("select count(*) from qualifications").fetchone()[0]
        if qualification_count == 0:
            main_company_id = db.execute("select id from companies where is_main = 1").fetchone()[0]
            sub_company_id = db.execute("select id from companies where name = '商丘市瑞隆土石方工程有限公司'").fetchone()[0]
            
            db.execute(
                """
                insert into qualifications (company_id, name, certificate_no, issue_date, expiry_date, is_long_term, notes)
                values (?, '建筑工程施工总承包一级', 'D241098765', '2023-05-10', '2028-12-31', 0, '集团主项资质')
                """,
                (main_company_id,)
            )
            db.execute(
                """
                insert into qualifications (company_id, name, certificate_no, issue_date, expiry_date, is_long_term, notes)
                values (?, '环保工程专业承包一级', 'D341054321', '2024-02-15', '2029-02-14', 0, '合作分包商专业资质')
                """,
                (sub_company_id,)
            )

        # 4. 插入精美财务凭证数据
        voucher_count = db.execute("select count(*) from vouchers").fetchone()[0]
        if voucher_count == 0:
            project_1 = db.execute("select id from projects where name = '郑州地铁6号线二期机电维保工程'").fetchone()
            project_2 = db.execute("select id from projects where name = '郑州市中原路绿化提升改造项目'").fetchone()
            
            if project_1 and project_2:
                db.execute(
                    """
                    insert into vouchers (project_id, voucher_date, voucher_type, amount, notes, entry_user)
                    values (?, '2026-05-20', '材料费用', 15200.00, '地铁6号线区间站采购阻燃铜芯电缆一批', '系统管理员')
                    """,
                    (project_1[0],)
                )
                db.execute(
                    """
                    insert into vouchers (project_id, voucher_date, voucher_type, amount, notes, entry_user)
                    values (?, '2026-05-24', '转账凭证', 4800.00, '中原路绿化工程 - 苗木运输运费报销', '系统管理员')
                    """,
                    (project_2[0],)
                )
                db.execute(
                    """
                    insert into vouchers (project_id, voucher_date, voucher_type, amount, notes, entry_user)
                    values (?, '2026-05-28', '油费', 2400.00, '项目车辆5月油卡充值报销凭证', '系统管理员')
                    """,
                    (project_1[0],)
                )
    db.commit()
