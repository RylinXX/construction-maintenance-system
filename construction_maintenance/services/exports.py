from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

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
