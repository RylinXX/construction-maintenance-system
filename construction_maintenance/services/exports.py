from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side


from construction_maintenance import repositories as repo

PEOPLE_HEADERS = [
    "姓名",
    "身份证号",
    "性别",
    "出生日期",
    "年龄",
    "电话",
    "住址",
    "岗位/工种",
    "银行卡号",
    "开户行",
    "入职/进场日期",
    "备注",
]


def build_people_workbook(path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "基础人员信息"
    sheet.append(PEOPLE_HEADERS)
    for person in repo.list_people():
        sheet.append(
            [
                person["name"],
                person["id_number"],
                person["gender"],
                person["birth_date"],
                person["age"],
                person["phone"],
                person["address"],
                person["job_type"],
                person["bank_card"],
                person["bank_name"],
                person["entry_date"],
                person["notes"],
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path


QUALIFICATION_HEADERS = ["公司", "资质名称", "证书编号", "发证日期", "到期日期", "长期有效", "附件", "备注"]


def build_qualification_workbook(path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "企业资质清单"
    sheet.append(QUALIFICATION_HEADERS)
    for item in repo.list_qualifications():
        sheet.append(
            [
                item["company_name"],
                item["name"],
                item["certificate_no"],
                item["issue_date"],
                item["expiry_date"],
                "是" if item["is_long_term"] else "否",
                item["attachment_path"],
                item["notes"],
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path


PROJECT_LEDGER_HEADERS = ["日期", "项目", "类型", "金额", "备注", "附件", "录入人"]


def build_project_ledger_workbook(path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "项目台账"
    sheet.append(PROJECT_LEDGER_HEADERS)
    for item in repo.list_vouchers():
        sheet.append(
            [
                item["voucher_date"],
                item["project_name"],
                item["voucher_type"],
                item["amount"],
                item["notes"],
                item["attachment_path"],
                item["entry_user"],
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path


def build_attendance_workbook(month: str, is_template: bool = False) -> Workbook:
    import calendar
    import datetime

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = f"{month} 考勤表"
    
    # 启用网格线显示
    sheet.views.sheetView[0].showGridLines = True

    try:
        year, month_num = map(int, month.split("-"))
    except (ValueError, TypeError):
        now = datetime.datetime.now()
        year, month_num = now.year, now.month
        month = f"{year:04d}-{month_num:02d}"

    _, total_days = calendar.monthrange(year, month_num)

    # 1. 构造表头列
    headers = ["姓名", "身份证号"]
    for day in range(1, total_days + 1):
        headers.append(f"{day}日")
    headers.extend(["出勤天数", "请假天数"])

    sheet.append(headers)

    # 2. 设置表头样式（精致的淡蓝色背景、加粗、居中对齐、细灰框）
    header_fill = PatternFill(start_color="e0f2fe", end_color="e0f2fe", fill_type="solid")
    header_font = Font(name="微软雅黑", size=11, bold=True, color="0f172a")
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="cbd5e1"),
        right=Side(style="thin", color="cbd5e1"),
        top=Side(style="thin", color="cbd5e1"),
        bottom=Side(style="thin", color="cbd5e1"),
    )

    for col_idx in range(1, len(headers) + 1):
        cell = sheet.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border

    # 3. 加载当前考勤名单
    people = repo.list_attendance_people()
    
    # 4. 加载当前月份的已有考勤数据
    attendance_dict = {}
    if not is_template:
        raw_attendance = repo.list_attendance_by_month(month)
        for record in raw_attendance:
            p_id = record["person_id"]
            date_str = record["work_date"]
            shift = record["shift_type"]
            if p_id not in attendance_dict:
                attendance_dict[p_id] = {}
            attendance_dict[p_id][date_str] = shift

    # 5. 循环写入数据行
    for r_idx, person in enumerate(people, start=2):
        row_data = [person["name"], person["id_number"]]
        day_count = 0
        leave_count = 0

        for d in range(1, total_days + 1):
            date_str = f"{month}-{d:02d}"
            shift = attendance_dict.get(person["id"], {}).get(date_str, None)
            if shift == "白班":
                row_data.append("白")
                day_count += 1
            elif shift == "夜班":
                row_data.append("夜")
                day_count += 1
            elif shift == "请假":
                row_data.append("假")
                leave_count += 1
            else:
                row_data.append("")

        row_data.extend([day_count, leave_count])
        sheet.append(row_data)

        # 为数据单元格应用精致的居中、边框及部分特殊标识字体样式
        for c_idx in range(1, len(headers) + 1):
            cell = sheet.cell(row=r_idx, column=c_idx)
            cell.alignment = center_align
            cell.border = thin_border
            cell.font = Font(name="微软雅黑", size=10)
            
            # 高亮标识白、夜、假
            val = cell.value
            if val == "白":
                cell.font = Font(name="微软雅黑", size=10, bold=True, color="0284c7")  # 科技天蓝
            elif val == "夜":
                cell.font = Font(name="微软雅黑", size=10, bold=True, color="1e40af")  # 深海蓝
            elif val == "假":
                cell.font = Font(name="微软雅黑", size=10, bold=True, color="d97706")  # 橙黄色

    # 6. 自适应设置列宽
    for col in sheet.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            val_str = str(cell.value or "")
            # 处理中文长度
            byte_len = len(val_str.encode("utf-8"))
            char_len = len(val_str)
            approx_len = char_len + (byte_len - char_len) // 2
            if approx_len > max_len:
                max_len = approx_len
        sheet.column_dimensions[col_letter].width = max(max_len + 3, 10)

    # 确保身份证号那列列宽较宽
    sheet.column_dimensions["B"].width = 22

    return workbook

