from __future__ import annotations

import datetime
from construction_maintenance.db import get_db, init_db
from construction_maintenance import repositories as repo

def test_salary_schema_and_tables(app):
    with app.app_context():
        init_db()
        db = get_db()
        
        # 1. 验证新表 exists
        tables = db.execute("select name from sqlite_master where type='table'").fetchall()
        table_names = {r["name"] for r in tables}
        assert "salary_payments" in table_names

        # 2. 验证 people 表字段
        people_cols = {r["name"] for r in db.execute("pragma table_info(people)").fetchall()}
        assert "salary_type" in people_cols
        assert "salary_rate" in people_cols


def test_person_salary_type_crud(app):
    with app.app_context():
        init_db()
        
        # 1. 新建人员带有薪水设置
        pid = repo.create_person({
            "name": "工资测试员",
            "id_number": "410101199001019999",
            "gender": "男",
            "age": 30,
            "salary_type": "月薪",
            "salary_rate": 8800.00
        })
        
        # 2. 读出并校验
        person = repo.get_db().execute("select * from people where id = ?", (pid,)).fetchone()
        assert person["salary_type"] == "月薪"
        assert person["salary_rate"] == 8800.00
        
        # 3. 更新薪水设置
        repo.update_person(pid, {
            "name": "工资测试员",
            "id_number": "410101199001019999",
            "gender": "男",
            "age": 30,
            "salary_type": "日薪",
            "salary_rate": 350.00
        })
        
        person = repo.get_db().execute("select * from people where id = ?", (pid,)).fetchone()
        assert person["salary_type"] == "日薪"
        assert person["salary_rate"] == 350.00


def test_salary_payments_crud(app):
    with app.app_context():
        init_db()
        
        # 1. 新建一个人员
        pid = repo.create_person({
            "name": "流水人员",
            "id_number": "410101199001018888",
            "gender": "男",
            "age": 35,
        })
        
        # 2. 增加一条预支流水
        pay_id = repo.create_salary_payment({
            "person_id": pid,
            "payment_date": "2026-06-10",
            "payment_type": "预支工资",
            "amount": 1200.00,
            "notes": "借生活费"
        })
        
        # 3. 校验列表
        payments = repo.list_salary_payments(person_id=pid)
        assert len(payments) == 1
        assert payments[0]["amount"] == 1200.00
        assert payments[0]["payment_type"] == "预支工资"
        assert payments[0]["notes"] == "借生活费"
        
        # 4. 删除该流水
        repo.delete_salary_payment(pay_id)
        payments = repo.list_salary_payments(person_id=pid)
        assert len(payments) == 0


def test_salary_calculations_rules(app):
    with app.app_context():
        init_db()
        db = get_db()
        
        # 我们在此新建 3 个测试人员，分别代表日薪、月薪、年薪
        pid_day = repo.create_person({
            "name": "日薪测试工",
            "id_number": "410101199001011111",
            "gender": "男",
            "salary_type": "日薪",
            "salary_rate": 300.00,
            "is_attendance": 1
        })
        
        pid_month = repo.create_person({
            "name": "月薪测试工",
            "id_number": "410101199001012222",
            "gender": "男",
            "salary_type": "月薪",
            "salary_rate": 9000.00,
            "is_attendance": 1
        })
        
        pid_year = repo.create_person({
            "name": "年薪测试工",
            "id_number": "410101199001013333",
            "gender": "男",
            "salary_type": "年薪",
            "salary_rate": 120000.00,
            "is_attendance": 1
        })
        
        # 我们录入 2026-06 月份的考勤
        # 1. 日薪工：出勤 5 天 (3天白班，2天夜班)
        repo.save_attendance(pid_day, "2026-06-01", "白班")
        repo.save_attendance(pid_day, "2026-06-02", "白班")
        repo.save_attendance(pid_day, "2026-06-03", "白班")
        repo.save_attendance(pid_day, "2026-06-04", "夜班")
        repo.save_attendance(pid_day, "2026-06-05", "夜班")
        
        # 2. 月薪工：请假 3 天
        repo.save_attendance(pid_month, "2026-06-10", "请假")
        repo.save_attendance(pid_month, "2026-06-11", "请假")
        repo.save_attendance(pid_month, "2026-06-12", "请假")
        
        # 3. 年薪工：出勤和请假不直接扣减，但我们记请假 2 天
        repo.save_attendance(pid_year, "2026-06-20", "请假")
        repo.save_attendance(pid_year, "2026-06-21", "请假")
        
        # 录入预支记录
        # 日薪工预支 500 元
        repo.create_salary_payment({
            "person_id": pid_day,
            "payment_date": "2026-06-15",
            "payment_type": "预支工资",
            "amount": 500.00,
            "notes": "买衣服"
        })
        
        # 月薪工发放了 3000 元
        repo.create_salary_payment({
            "person_id": pid_month,
            "payment_date": "2026-06-25",
            "payment_type": "工资发放",
            "amount": 3000.00,
            "notes": "发部分尾款"
        })

        # 进行计算核算
        summary = repo.get_salary_summary_by_month("2026-06")
        summary_map = {item["person_id"]: item for item in summary}
        
        # 1. 验证日薪工
        # 出勤 5 天，日薪 300，应发 1500。预支 500，尾款 1000。
        day_item = summary_map[pid_day]
        assert day_item["earnings"] == 1500.00
        assert day_item["advance"] == 500.00
        assert day_item["balance"] == 1000.00
        
        # 2. 验证月薪工
        # 2026-06 共有 30 天，基本月薪 9000，请假 3 天。
        # 扣减 = 3 * (9000 / 30) = 900。应发 = 8100。已发 3000，尾款 5100。
        month_item = summary_map[pid_month]
        assert month_item["earnings"] == 8100.00
        assert month_item["payout"] == 3000.00
        assert month_item["balance"] == 5100.00
        
        # 3. 验证年薪工
        # 年薪 120000，应发月薪 = 10000。没有预支，尾款 10000。
        year_item = summary_map[pid_year]
        assert year_item["earnings"] == 10000.00
        assert year_item["balance"] == 10000.00
