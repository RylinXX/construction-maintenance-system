import os
import sys
import random
from datetime import datetime, timedelta

# 设置环境变量以便加载正确的配置
os.environ['FLASK_APP'] = 'construction_maintenance.app:create_app()'

from construction_maintenance.app import create_app
from construction_maintenance.db import get_db

app = create_app()

def mask_id_number(id_num):
    if not id_num or len(id_num) < 15:
        return "110101" + "*" * 8 + f"{random.randint(1000, 9999)}"
    return id_num[:6] + "********" + id_num[-4:]

def mask_phone(phone_num):
    if not phone_num or len(phone_num) < 11:
        prefix = random.choice(["138", "139", "150", "186", "177", "189"])
        return f"{prefix}****{random.randint(1000, 9999)}"
    return phone_num[:3] + "****" + phone_num[-4:]

def mask_bank_card(card_num):
    if not card_num or len(card_num) < 12:
        return f"6222 **** **** {random.randint(1000, 9999)}"
    clean = str(card_num).replace(" ", "")
    if len(clean) >= 16:
        return f"{clean[:4]} **** **** {clean[-4:]}"
    return f"{clean[:4]} **** {clean[-4:]}"

def run():
    with app.app_context():
        db = get_db()
        cur = db.cursor()

        print("--- 1. 脱敏现有人员数据 ---")
        cur.execute("SELECT id, name, id_number, phone, bank_card FROM people")
        existing_people = cur.fetchall()
        
        for person in existing_people:
            pid, name, id_num, phone, bank = person
            masked_id = mask_id_number(id_num)
            masked_ph = mask_phone(phone)
            masked_bk = mask_bank_card(bank)
            
            cur.execute("""
                UPDATE people 
                SET id_number = ?, phone = ?, bank_card = ?
                WHERE id = ?
            """, (masked_id, masked_ph, masked_bk, pid))
            
        print(f"成功脱敏现有 {len(existing_people)} 条人员记录。")

        print("--- 2. 新增丰富演示人员数据 ---")
        job_roles = [
            ('项目经理', '月薪', (15000, 25000)),
            ('技术负责人', '月薪', (12000, 20000)),
            ('安全员', '月薪', (7000, 11000)),
            ('施工员', '月薪', (8000, 13000)),
            ('测量员', '日薪', (450, 650)),
            ('资料员', '月薪', (6000, 9000)),
            ('质量员', '月薪', (7500, 12000)),
            ('钩机司机', '日薪', (380, 550)),
            ('铲车司机', '日薪', (350, 500)),
            ('水车司机', '日薪', (300, 420)),
            ('钢筋工班长', '日薪', (400, 550)),
            ('木工', '日薪', (380, 500)),
            ('电工', '日薪', (350, 480)),
            ('焊工', '日薪', (380, 520)),
            ('杂工/小工', '日薪', (220, 320)),
            ('机械维修工', '日薪', (350, 480)),
        ]

        bank_names = ['中国工商银行', '中国建设银行', '中国农业银行', '中国银行', '招商银行', '交通银行']

        surnames = ['张', '王', '李', '赵', '陈', '刘', '杨', '黄', '吴', '周', '徐', '孙', '马', '朱', '胡', '郭', '林', '何', '高', '罗']
        given_names = ['建国', '志强', '海峰', '立业', '小明', '文杰', '国庆', '德华', '家豪', '正宇', '云龙', '天宇', '振华', '伟明', '少华', '永强', '文龙', '宝亮', '金龙', '胜强']

        added_count = 0
        for i in range(25): # 生成 25 条演示人员
            name = random.choice(surnames) + random.choice(given_names)
            gender = random.choice(['男', '男', '男', '女'])
            age = random.randint(24, 56)
            birth_year = 2026 - age
            birth_date = f"{birth_year}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
            
            id_prefix = random.choice(['110101', '410101', '370101', '130101', '510101'])
            raw_id = f"{id_prefix}{birth_year}{random.randint(10, 12):02d}{random.randint(10, 28):02d}{random.randint(1000, 9999)}"
            masked_id = mask_id_number(raw_id)
            
            phone = f"13{random.randint(0, 9)}{random.randint(1000, 9999)}{random.randint(1000, 9999)}"
            masked_ph = mask_phone(phone)
            
            bank_name = random.choice(bank_names)
            bank_card = f"6222{random.randint(1000, 9999)}{random.randint(1000, 9999)}{random.randint(1000, 9999)}"
            masked_bk = mask_bank_card(bank_card)

            job_type, salary_type, rate_range = random.choice(job_roles)
            rate = float(random.randint(rate_range[0] // 10, rate_range[1] // 10) * 10)

            entry_days_ago = random.randint(10, 365)
            entry_date = (datetime.now() - timedelta(days=entry_days_ago)).strftime('%Y-%m-%d')
            notes = random.choice(['持特种作业操作证', '已签署安全防护责任书', '具备多年工程现场经验', '资质审核通过', '常规人员备案'])

            # 避免 id_number 唯一键冲突
            cur.execute("SELECT id FROM people WHERE id_number = ?", (masked_id,))
            if cur.fetchone():
                continue

            cur.execute("""
                INSERT INTO people (
                    name, id_number, gender, birth_date, age, phone, 
                    address, job_type, bank_card, bank_name, entry_date, 
                    notes, review_status, is_attendance, salary_type, salary_rate
                ) VALUES (?, ?, ?, ?, ?, ?, '北京市海湾区建设基地', ?, ?, ?, ?, ?, '已确认', 1, ?, ?)
            """, (name, masked_id, gender, birth_date, age, masked_ph, job_type, masked_bk, bank_name, entry_date, notes, salary_type, rate))
            added_count += 1

        db.commit()
        print(f"成功新增 {added_count} 条丰富的人员演示数据。")

if __name__ == '__main__':
    run()
