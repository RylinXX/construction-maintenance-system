# -*- coding: utf-8 -*-
"""
数据灌入与完善脚本
使用 Flask App Context 保证数据库结构已被升级，然后向数据库中补全：
- 2 家公司
- 12 个项目
- 16 位真实的施工人员，及其 2026-05 与 2026-06 的考勤和工资收支流水
"""
import sys
from pathlib import Path

# 将项目根目录加入到 PATH
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from construction_maintenance.app import create_app
from construction_maintenance.db import get_db

def import_data():
    app = create_app()
    with app.app_context():
        db = get_db()
        print("正在获取数据库连接...")
        
        # 1. 导入 2 家公司
        companies = [
            ("北京营力特建筑工程有限公司", "91110108MA01XXXXXX", "营力特法人", "13811112222", "分包合作商（截图资料公司）", 0),
            ("北京倍越兴建筑工程有限公司", "91110108MA02YYYYYY", "倍越兴法人", "13933334444", "分包合作商（截图资料公司）", 0)
        ]

        company_ids = {}
        for name, credit_code, legal_person, phone, notes, is_main in companies:
            row = db.execute("select id from companies where name = ?", (name,)).fetchone()
            if row:
                company_ids[name] = row["id"]
                print(f"公司已存在：{name} (ID: {row['id']})")
            else:
                cursor = db.execute(
                    """
                    insert into companies (name, credit_code, legal_person, phone, notes, is_main)
                    values (?, ?, ?, ?, ?, ?)
                    """,
                    (name, credit_code, legal_person, phone, notes, is_main)
                )
                company_ids[name] = cursor.lastrowid
                print(f"成功导入公司：{name} (ID: {company_ids[name]})")

        # 2. 导入 12 个项目
        projects = [
            ("中央电视总台项目", "北京营力特建筑工程有限公司", "进行中", "中央电视台", "2026-01-01", "2026-12-31", "包含中央电视总台项目资料"),
            ("军庄项目", "北京营力特建筑工程有限公司", "进行中", "军庄建设方", "2026-02-01", "2026-12-31", "包含军庄资料"),
            ("衙门口项目", "北京倍越兴建筑工程有限公司", "进行中", "衙门口建设方", "2026-03-01", "2026-12-31", "包含衙门口资料"),
            ("老东山项目", "北京倍越兴建筑工程有限公司", "已完工", "老东山建设方", "2025-05-01", "2026-05-01", "老东山资料-完工"),
            ("通州潞城项目", "北京营力特建筑工程有限公司", "进行中", "通州区潞城建设", "2026-04-01", "2026-12-31", "通州潞城项目资料"),
            ("内蒙二期项目", "北京倍越兴建筑工程有限公司", "已完工", "内蒙电力", "2025-06-01", "2026-05-01", "内蒙二期项目-完工"),
            ("首师大八里庄项目", "北京营力特建筑工程有限公司", "进行中", "首师大", "2026-04-15", "2026-12-31", "首师大八里庄项目资料"),
            ("北理工项目", "北京倍越兴建筑工程有限公司", "已完工", "北京理工大学", "2025-07-01", "2026-05-01", "北理工项目-完工"),
            ("顺义项目", "北京营力特建筑工程有限公司", "进行中", "顺义建设方", "2026-05-01", "2026-12-31", "顺义项目资料"),
            ("通州六合工地项目", "北京倍越兴建筑工程有限公司", "进行中", "通州区六合", "2026-03-10", "2026-12-31", "通州六合工地"),
            ("新兴项目", "北京倍越兴建筑工程有限公司", "进行中", "新兴建设方", "2026-02-15", "2026-12-31", "新兴资料"),
            ("梧桐苑项目", "北京营力特建筑工程有限公司", "进行中", "梧桐苑房地产", "2026-01-10", "2026-12-31", "梧桐苑项目资料"),
        ]

        project_ids = {}
        for p_name, comp_name, status, owner, start_date, end_date, notes in projects:
            comp_id = company_ids[comp_name]
            row = db.execute("select id from projects where name = ?", (p_name,)).fetchone()
            if row:
                project_ids[p_name] = row["id"]
                print(f"项目已存在：{p_name} (ID: {row['id']})")
            else:
                cursor = db.execute(
                    """
                    insert into projects (company_id, name, status, owner, start_date, end_date, notes)
                    values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (comp_id, p_name, status, owner, start_date, end_date, notes)
                )
                project_ids[p_name] = cursor.lastrowid
                print(f"成功导入项目：{p_name} (ID: {project_ids[p_name]})")

        # 3. 导入 16 位营力特公司的真实施工人员
        people_data = [
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

        person_ids = {}
        for name, id_num, gender, birth_d, age, phone, addr, sal_type, sal_rate in people_data:
            row = db.execute("select id from people where id_number = ?", (id_num,)).fetchone()
            if row:
                person_ids[name] = row["id"]
                db.execute(
                    """
                    update people
                    set name = ?, gender = ?, birth_date = ?, age = ?, phone = ?, address = ?, salary_type = ?, salary_rate = ?
                    where id = ?
                    """,
                    (name, gender, birth_d, age, phone, addr, sal_type, sal_rate, row["id"])
                )
                print(f"人员已存在，已更新其信息：{name} (ID: {row['id']})")
            else:
                cursor = db.execute(
                    """
                    insert into people (name, id_number, gender, birth_date, age, phone, address, job_type, entry_date, review_status, salary_type, salary_rate)
                    values (?, ?, ?, ?, ?, ?, ?, '普工', '2026-05-24', '已确认', ?, ?)
                    """,
                    (name, id_num, gender, birth_d, age, phone, addr, sal_type, sal_rate)
                )
                person_ids[name] = cursor.lastrowid
                print(f"成功导入人员：{name} (ID: {person_ids[name]})")

        # 4. 导入考勤
        print("正在导入考勤与工资流水数据...")
        
        def add_attendance(p_name, w_date, shift):
            p_id = person_ids[p_name]
            exists = db.execute("select id from attendance where person_id = ? and work_date = ?", (p_id, w_date)).fetchone()
            if not exists:
                db.execute(
                    "insert into attendance (person_id, work_date, shift_type, notes) values (?, ?, ?, ?)",
                    (p_id, w_date, shift, "系统批量导入")
                )

        for name in person_ids.keys():
            name_hash = sum(ord(c) for c in name)
            for day in range(24, 32):
                date_str = f"2026-05-{day}"
                if name_hash % 7 == 0 and day in (26, 30):
                    add_attendance(name, date_str, "请假")
                elif name_hash % 5 == 0 and day == 28:
                    add_attendance(name, date_str, "请假")
                elif (name_hash + day) % 2 == 0:
                    add_attendance(name, date_str, "白班")
                else:
                    add_attendance(name, date_str, "夜班")

            for day in range(1, 4):
                date_str = f"2026-06-0{day}"
                if (name_hash + day) % 3 == 0:
                    add_attendance(name, date_str, "白班")
                elif (name_hash + day) % 3 == 1:
                    add_attendance(name, date_str, "夜班")
                else:
                    add_attendance(name, date_str, "请假")

        # 5. 导入预支工资和发放流水数据
        def add_payment(p_name, pay_date, pay_type, amount, notes):
            p_id = person_ids[p_name]
            exists = db.execute(
                """
                select id from salary_payments 
                where person_id = ? and payment_date = ? and payment_type = ? and amount = ?
                """,
                (p_id, pay_date, pay_type, amount)
            ).fetchone()
            if not exists:
                db.execute(
                    """
                    insert into salary_payments (person_id, payment_date, payment_type, amount, notes)
                    values (?, ?, ?, ?, ?)
                    """,
                    (p_id, pay_date, pay_type, amount, notes)
                )
                print(f"为 {p_name} 插入流水：{pay_type} {amount}元")

        # 5月份预支
        add_payment("谢伟", "2026-05-28", "预支工资", 1000.00, "5月份生活费预支")
        add_payment("张文刚", "2026-05-29", "预支工资", 1500.00, "预支生活费")
        add_payment("汪保伦", "2026-05-28", "预支工资", 1200.00, "新入职借支")
        add_payment("谢瑞鸣", "2026-05-30", "预支工资", 500.00, "买生活用品借支")
        add_payment("方强", "2026-05-29", "预支工资", 800.00, "预支零花钱")
        add_payment("张坤", "2026-05-30", "预支工资", 600.00, "买衣物预支")

        # 6月份预支
        add_payment("谢伟", "2026-06-02", "预支工资", 500.00, "6月份零花钱借支")
        add_payment("张文刚", "2026-06-02", "预支工资", 1000.00, "6月租房补贴与生活费借支")
        add_payment("马士银", "2026-06-02", "预支工资", 400.00, "6月预支")
        add_payment("黄保清", "2026-06-01", "预支工资", 300.00, "借支")

        # 5月份工资发放
        add_payment("谢瑞鸣", "2026-06-02", "工资发放", 1500.00, "结清5月份工钱")
        add_payment("黄林刚", "2026-06-02", "工资发放", 1200.00, "发放5月工资")
        add_payment("李效良", "2026-06-02", "工资发放", 1000.00, "结清5月部分工钱")

        db.commit()
        print("所有数据导入并提交成功！")

if __name__ == "__main__":
    import_data()
