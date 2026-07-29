import random
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
import os
import sys

# 设置基础路径以适配开发环境和生产 Docker 环境
BASE_DIR = Path(__file__).parent.parent
INSTANCE_DIR = Path(os.environ.get('CAM_INSTANCE_DIR', BASE_DIR / 'instance'))
DB_PATH = INSTANCE_DIR / 'construction.sqlite3'

def generate_data():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)

    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get existing projects
    cur.execute("SELECT id, name FROM projects")
    projects = cur.fetchall()
    if not projects:
        print("No projects found, skipping contracts generation.")
    else:
        # Generate Contracts
        contract_types = ['工程总承包合同', '劳务分包合同', '材料采购合同', '机械租赁合同', '设计合同', '监理合同']
        contract_status_notes = ['已盖章，原件在财务处', '缺对方签章', '正在走法务审批流', '补充协议已归档', '附带补充条款', '常规合同']
        
        contracts_to_insert = []
        for project_id, project_name in projects:
            num_contracts = random.randint(3, 8)
            for i in range(num_contracts):
                c_type = random.choice(contract_types)
                name = f"{project_name}-{c_type}-{datetime.now().strftime('%Y%m')}-{i+1:03d}"
                notes = random.choice(contract_status_notes)
                contracts_to_insert.append((project_id, name, c_type, notes))
        
        cur.executemany("""
            INSERT INTO contracts (project_id, name, contract_type, notes)
            VALUES (?, ?, ?, ?)
        """, contracts_to_insert)
        print(f"Generated {len(contracts_to_insert)} mock contracts.")

    # Get existing people
    cur.execute("SELECT id, name FROM people")
    people = cur.fetchall()
    if not people:
        print("No people found, skipping attendance generation.")
    else:
        # Generate Attendance for the last 30 days
        shift_types = ['全天', '半天', '请假', '旷工', '夜班', '加班(小时)']
        attendance_to_insert = []
        
        today = datetime.now()
        
        # Determine existing attendance to avoid unique constraint (person_id, work_date)
        cur.execute("SELECT person_id, work_date FROM attendance")
        existing_attendance = set(cur.fetchall())
        
        for person_id, person_name in people:
            # Randomly select a subset of days to work in the past 30 days
            for days_ago in range(30):
                if random.random() < 0.7:  # 70% attendance rate
                    work_date = (today - timedelta(days=days_ago)).strftime('%Y-%m-%d')
                    if (person_id, work_date) not in existing_attendance:
                        shift = random.choices(shift_types, weights=[80, 5, 5, 2, 5, 3])[0]
                        notes = ''
                        if shift == '请假':
                            notes = '事假'
                        elif shift == '半天':
                            notes = '下午请假'
                        attendance_to_insert.append((person_id, work_date, shift, notes))
                        existing_attendance.add((person_id, work_date))
                        
        cur.executemany("""
            INSERT INTO attendance (person_id, work_date, shift_type, notes)
            VALUES (?, ?, ?, ?)
        """, attendance_to_insert)
        print(f"Generated {len(attendance_to_insert)} mock attendance records.")

    conn.commit()
    conn.close()
    print("Mock data generation completed successfully.")

if __name__ == '__main__':
    generate_data()
