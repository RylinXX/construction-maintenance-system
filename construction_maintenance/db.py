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

DEFAULT_SYSTEM_SETTINGS = {
    "system_name": "建筑工程维护系统",
    "organization_name": "工程运营管理中心",
    "support_contact": "",
    "session_timeout_minutes": "120",
}


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
            salary_type text not null default '日薪',
            salary_rate real not null default 0.0,
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

        create table if not exists contracts (
            id integer primary key autoincrement,
            project_id integer not null references projects(id),
            name text not null,
            contract_type text not null,
            attachment_path text not null default '',
            notes text not null default '',
            created_at text not null default current_timestamp
        );

        create table if not exists salary_payments (
            id integer primary key autoincrement,
            person_id integer not null references people(id) on delete cascade,
            payment_date text not null,
            payment_type text not null,
            amount real not null check(amount >= 0),
            notes text not null default '',
            created_at text not null default current_timestamp
        );

        create table if not exists salary_sheets (
            id integer primary key autoincrement,
            person_id integer not null references people(id) on delete cascade,
            settle_month text not null,
            should_work_days real not null default 30.0,
            actual_work_days real not null default 30.0,
            salary_rate real not null default 0.0,
            earnings real not null default 0.0,
            paid_amount real not null default 0.0,
            notes text not null default '',
            created_at text not null default current_timestamp
        );

        create table if not exists admin_users (
            id integer primary key autoincrement,
            username text not null collate nocase unique,
            display_name text not null,
            password_hash text not null,
            role text not null default 'admin'
                check (role in ('admin', 'super_admin')),
            is_active integer not null default 1
                check (is_active in (0, 1)),
            must_change_password integer not null default 0
                check (must_change_password in (0, 1)),
            last_login_at text,
            created_at text not null default current_timestamp,
            updated_at text not null default current_timestamp
        );

        create table if not exists system_settings (
            key text primary key,
            value text not null default '',
            updated_at text not null default current_timestamp
        );
        """
    )
    db.executemany(
        """
        insert or ignore into system_settings (key, value)
        values (?, ?)
        """,
        DEFAULT_SYSTEM_SETTINGS.items(),
    )

    bootstrap_username = str(current_app.config.get("ADMIN_USERNAME") or "").strip()
    bootstrap_password_hash = str(
        current_app.config.get("ADMIN_PASSWORD_HASH") or ""
    ).strip()
    admin_count = db.execute("select count(*) from admin_users").fetchone()[0]
    if admin_count == 0 and bootstrap_username and bootstrap_password_hash:
        db.execute(
            """
            insert into admin_users (
                username, display_name, password_hash, role, is_active
            )
            values (?, '系统管理员', ?, 'super_admin', 1)
            """,
            (bootstrap_username, bootstrap_password_hash),
        )
    elif bootstrap_username and bootstrap_password_hash:
        active_super_admins = db.execute(
            """
            select count(*)
            from admin_users
            where role = 'super_admin' and is_active = 1
            """
        ).fetchone()[0]
        if active_super_admins == 0:
            bootstrap_user = db.execute(
                "select id from admin_users where username = ?",
                (bootstrap_username,),
            ).fetchone()
            if bootstrap_user:
                db.execute(
                    """
                    update admin_users
                    set password_hash = ?, role = 'super_admin', is_active = 1,
                        must_change_password = 0,
                        updated_at = current_timestamp
                    where id = ?
                    """,
                    (bootstrap_password_hash, bootstrap_user["id"]),
                )
            else:
                db.execute(
                    """
                    insert into admin_users (
                        username, display_name, password_hash, role, is_active
                    )
                    values (?, '系统管理员', ?, 'super_admin', 1)
                    """,
                    (bootstrap_username, bootstrap_password_hash),
                )

    people_columns = {
        row["name"] for row in db.execute("pragma table_info(people)").fetchall()
    }
    if "id_card_path" not in people_columns:
        db.execute("alter table people add column id_card_path text not null default ''")
    if "is_attendance" not in people_columns:
        db.execute("alter table people add column is_attendance integer not null default 1")
    if "salary_type" not in people_columns:
        db.execute("alter table people add column salary_type text not null default '日薪'")
    if "salary_rate" not in people_columns:
        db.execute("alter table people add column salary_rate real not null default 0.0")

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
                ("谢瑞鸣", "411503200102019635", "男", "2001-02-01", 25, "17710665069", "河南省信阳市平桥区", "日薪", 310.00),
                ("谢伟", "413001198310156513", "男", "1983-10-15", 43, "17739720017", "河南省信阳市", "月薪", 7800.00),
                ("王维秋", "372926198705073977", "男", "1987-05-07", 39, "18678587973", "山东省菏泽市巨野县", "日薪", 330.00),
                ("张坤", "341281198602166097", "男", "1986-02-16", 40, "13683356253", "安徽省亳州市", "日薪", 350.00),
                ("黄保清", "413023197210084210", "男", "1972-10-08", 54, "15552041689", "河南省信阳市平桥区", "日薪", 280.00),
                ("黄保林", "413023198101244232", "男", "1981-01-24", 45, "13671159122", "河南省信阳市平桥区", "日薪", 290.00),
                ("黄玉东", "411503200412026750", "男", "2004-12-02", 22, "15188559208", "河南省信阳市平桥区", "日薪", 260.00),
                ("张文刚", "232303198611153839", "男", "1986-11-15", 40, "13403769906", "黑龙江省绥化市肇东市", "月薪", 8000.00),
                ("马士银", "411503198205210619", "男", "1982-05-21", 44, "15937658121", "河南省信阳市平桥区", "日薪", 300.00),
                ("谢抒洋", "411503200306110633", "男", "2003-06-11", 23, "15937658121", "河南省信阳市平桥区", "日薪", 290.00),
                ("谢俊", "411503200502284235", "男", "2005-02-28", 21, "17610677658", "河南省信阳市平桥区", "日薪", 270.00),
                ("谢金斌", "511623199102033313", "男", "1991-02-03", 35, "18161151333", "四川省广安市邻水县", "日薪", 320.00),
                ("李效良", "372926198712023935", "男", "1987-12-02", 39, "15552041689", "山东省菏泽市巨野县", "日薪", 310.00),
                ("方强", "411503199811114218", "男", "1998-11-11", 28, "18337986537", "河南省信阳市平桥区邢集镇周楼村陈庄村民组49号", "日薪", 340.00),
                ("黄林刚", "411503199105034210", "男", "1991-05-03", 35, "15738696655", "河南省信阳市平桥区邢集镇高庙村大黄庄组32号", "日薪", 300.00),
                ("汪保伦", "411503199504104239", "男", "1995-04-10", 31, "13673600372", "河南省信阳市平桥区邢集镇康庄村汪庄村民组8号", "月薪", 7500.00),
            ]
            for name, id_num, gen, birth, age, ph, addr, sal_t, sal_r in test_people:
                cursor = db.execute(
                    """
                    insert into people (name, id_number, gender, birth_date, age, phone, address, job_type, entry_date, review_status, salary_type, salary_rate)
                    values (?, ?, ?, ?, ?, ?, ?, '普工', '2026-05-24', '已确认', ?, ?)
                    """,
                    (name, id_num, gen, birth, age, ph, addr, sal_t, sal_r)
                )
                person_id = cursor.lastrowid
                
                attendance_dates = []
                name_hash = sum(ord(c) for c in name)
                
                # 5月考勤 (24号~31号)
                for d in range(24, 32):
                    date_str = f"2026-05-{d}"
                    if name_hash % 7 == 0 and d in (26, 30):
                        attendance_dates.append((date_str, "请假"))
                    elif name_hash % 5 == 0 and d == 28:
                        attendance_dates.append((date_str, "请假"))
                    else:
                        attendance_dates.append((date_str, "上班"))
                
                # 6月考勤 (1号~3号)
                for d in range(1, 4):
                    date_str = f"2026-06-0{d}"
                    if (name_hash + d) % 3 == 2:
                        attendance_dates.append((date_str, "请假"))
                    else:
                        attendance_dates.append((date_str, "上班"))

                db.executemany(
                    "insert into attendance (person_id, work_date, shift_type) values (?, ?, ?)",
                    [(person_id, date, shift) for date, shift in attendance_dates],
                )

        # 扩充项目、资质、企业与费用凭证演示数据 (用于全系统演示)
        # 1. 升级公司名称及插入关联外包企业
        db.execute("update companies set name = '河南建工第八建设集团有限公司' where is_main = 1 and name = '主公司'")
        
        # 插入截图中的新增公司
        for comp_name in ["北京营力特建筑工程有限公司", "北京倍越兴建筑工程有限公司"]:
            exists = db.execute("select 1 from companies where name = ?", (comp_name,)).fetchone()
            if not exists:
                db.execute(
                    """
                    insert into companies (name, credit_code, legal_person, phone, notes, is_main)
                    values (?, '', '', '', '分包合作商', 0)
                    """,
                    (comp_name,)
                )

        # 2. 插入精美演示项目 (截图的 12 个项目)
        project_count = db.execute("select count(*) from projects").fetchone()[0]
        if project_count == 0:
            ylt_row = db.execute("select id from companies where name = '北京营力特建筑工程有限公司'").fetchone()
            byx_row = db.execute("select id from companies where name = '北京倍越兴建筑工程有限公司'").fetchone()
            main_company_id = db.execute("select id from companies where is_main = 1").fetchone()[0]
            
            ylt_id = ylt_row[0] if ylt_row else main_company_id
            byx_id = byx_row[0] if byx_row else main_company_id
            
            projects_data = [
                (ylt_id, "中央电视总台项目", "进行中", "中央电视台", "2026-01-01", "2026-12-31", "包含中央电视总台项目资料"),
                (ylt_id, "军庄项目", "进行中", "军庄建设方", "2026-02-01", "2026-12-31", "包含军庄资料"),
                (byx_id, "衙门口项目", "进行中", "衙门口建设方", "2026-03-01", "2026-12-31", "包含衙门口资料"),
                (byx_id, "老东山项目", "已完工", "老东山建设方", "2025-05-01", "2026-05-01", "老东山资料-完工"),
                (ylt_id, "通州潞城项目", "进行中", "通州区潞城建设", "2026-04-01", "2026-12-31", "通州潞城项目资料"),
                (byx_id, "内蒙二期项目", "已完工", "内蒙电力", "2025-06-01", "2026-05-01", "内蒙二期项目-完工"),
                (ylt_id, "首师大八里庄项目", "进行中", "首师大", "2026-04-15", "2026-12-31", "首师大八里庄项目资料"),
                (byx_id, "北理工项目", "已完工", "北京理工大学", "2025-07-01", "2026-05-01", "北理工项目-完工"),
                (ylt_id, "顺义项目", "进行中", "顺义建设方", "2026-05-01", "2026-12-31", "顺义项目资料"),
                (byx_id, "通州六合工地项目", "进行中", "通州区六合", "2026-03-10", "2026-12-31", "通州六合工地"),
                (byx_id, "新兴项目", "进行中", "新兴建设方", "2026-02-15", "2026-12-31", "新兴资料"),
                (ylt_id, "梧桐苑项目", "进行中", "梧桐苑房地产", "2026-01-10", "2026-12-31", "梧桐苑项目资料"),
            ]
            for comp_id, p_name, status, owner, start_d, end_d, notes in projects_data:
                db.execute(
                    """
                    insert into projects (company_id, name, status, owner, start_date, end_date, notes)
                    values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (comp_id, p_name, status, owner, start_d, end_d, notes)
                )

        # 3. 插入精美资质数据
        qualification_count = db.execute("select count(*) from qualifications").fetchone()[0]
        if qualification_count == 0:
            main_company_id = db.execute("select id from companies where is_main = 1").fetchone()[0]
            sub_company_id = db.execute("select id from companies where name = '北京营力特建筑工程有限公司'").fetchone()
            sub_company_id = sub_company_id[0] if sub_company_id else main_company_id
            
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
            project_1 = db.execute("select id from projects where name = '中央电视总台项目'").fetchone()
            project_2 = db.execute("select id from projects where name = '军庄项目'").fetchone()
            
            if project_1 and project_2:
                db.execute(
                    """
                    insert into vouchers (project_id, voucher_date, voucher_type, amount, notes, entry_user)
                    values (?, '2026-05-20', '材料费用', 15200.00, '中央电视总台项目采购电缆一批', '系统管理员')
                    """,
                    (project_1[0],)
                )
                db.execute(
                    """
                    insert into vouchers (project_id, voucher_date, voucher_type, amount, notes, entry_user)
                    values (?, '2026-05-24', '转账凭证', 4800.00, '军庄项目 - 运输运费报销', '系统管理员')
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

        # 5. 插入合同演示数据
        contract_count = db.execute("select count(*) from contracts").fetchone()[0]
        if contract_count == 0:
            project_1 = db.execute("select id from projects where name = '中央电视总台项目'").fetchone()
            project_2 = db.execute("select id from projects where name = '军庄项目'").fetchone()
            if project_1 and project_2:
                db.execute(
                    """
                    insert into contracts (project_id, name, contract_type, attachment_path, notes)
                    values (?, '中央电视总台项目劳务分包合同', '劳务合同', 'contract_metro_labor.pdf', '与北京营力特签署的劳务合同')
                    """,
                    (project_1[0],)
                )
                db.execute(
                    """
                    insert into contracts (project_id, name, contract_type, attachment_path, notes)
                    values (?, '军庄项目绿化苗木采购合同', '材料商合同', 'contract_green_tree.pdf', '向百卉园艺采购合同')
                    """,
                    (project_2[0],)
                )

        # 6. 以幂等方式插入收付流水
        # 辅助函数，确保重复初始化时不污染数据库
        def safe_insert_payment(person_name, p_date, p_type, p_amount, p_notes):
            p = db.execute("select id from people where name = ?", (person_name,)).fetchone()
            if p:
                pid = p[0]
                exists = db.execute(
                    "select 1 from salary_payments where person_id = ? and payment_date = ? and payment_type = ? and amount = ?",
                    (pid, p_date, p_type, p_amount)
                ).fetchone()
                if not exists:
                    db.execute(
                        "insert into salary_payments (person_id, payment_date, payment_type, amount, notes) values (?, ?, ?, ?, ?)",
                        (pid, p_date, p_type, p_amount, p_notes)
                    )

        # 5月流水
        safe_insert_payment("谢伟", "2026-05-28", "预支工资", 1000.00, "5月份生活费预支")
        safe_insert_payment("张文刚", "2026-05-29", "预支工资", 1500.00, "预支生活费")
        safe_insert_payment("汪保伦", "2026-05-28", "预支工资", 1200.00, "新入职借支")
        safe_insert_payment("谢瑞鸣", "2026-05-30", "预支工资", 500.00, "买生活用品借支")
        safe_insert_payment("方强", "2026-05-29", "预支工资", 800.00, "预支零花钱")
        safe_insert_payment("张坤", "2026-05-30", "预支工资", 600.00, "买衣物预支")
        
        # 6月流水
        safe_insert_payment("谢伟", "2026-06-02", "预支工资", 500.00, "6月份零花钱借支")
        safe_insert_payment("张文刚", "2026-06-02", "预支工资", 1000.00, "6月租房补贴与生活费借支")
        safe_insert_payment("马士银", "2026-06-02", "预支工资", 400.00, "6月预支")
        safe_insert_payment("黄保清", "2026-06-01", "预支工资", 300.00, "借支")
        
        # 工资发放结清5月份
        safe_insert_payment("谢瑞鸣", "2026-06-02", "工资发放", 1500.00, "结清5月份工钱")
        safe_insert_payment("黄林刚", "2026-06-02", "工资发放", 1200.00, "发放5月工资")
        safe_insert_payment("李效良", "2026-06-02", "工资发放", 1000.00, "结清5月部分工钱")

    # 对历史考勤数据进行统一订正，将以往所有的“白班”和“夜班”全部更新为“上班”
    db.execute("update attendance set shift_type = '上班' where shift_type in ('白班', '夜班')")
    db.commit()

