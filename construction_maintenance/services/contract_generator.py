from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime

# Standard HTML Templates for Contract Generation
TEMPLATES = [
    {
        "id": "01_labor_contract",
        "name": "公司标准《劳务合同》（不交社保版）",
        "category": "人员合同",
        "description": "基于公司官方 DOCX 标准研发，包含双方协商、劳务内容、报酬支付、不建立劳动关系与不缴社保特别约定及公章/签字处。",
        "template_filename": "01_labor_contract.html"
    },
    {
        "id": "02_subcontract_agreement",
        "name": "建筑施工劳动合同书（规范全日制版）",
        "category": "人员合同",
        "description": "适用于全日制及项目常驻管理与技术人员的规范劳动合同。",
        "template_filename": "02_subcontract_agreement.html"
    },
    {
        "id": "03_temporary_work_agreement",
        "name": "工程施工班组用工协议书",
        "category": "劳务合同",
        "description": "适用于班组及专业劳务人员项目包干或按日结算的施工用工协议。",
        "template_filename": "03_temporary_work_agreement.html"
    },
    {
        "id": "04_machinery_lease_contract",
        "name": "工程机械设备与司机租赁合同",
        "category": "其它",
        "description": "适用于钩机、铲车、水车等机械设备及其操作司机的机械租赁合同。",
        "template_filename": "04_machinery_lease_contract.html"
    }
]

def list_contract_templates():
    return TEMPLATES

def get_template_by_id(template_id: str):
    for t in TEMPLATES:
        if t["id"] == template_id:
            return t
    return TEMPLATES[0]

def render_contract_html(template_id: str, person: dict, project: dict, signing_date: str = None) -> str:
    template_info = get_template_by_id(template_id)
    if not signing_date:
        signing_date = datetime.now().strftime("%Y年%m月%d日")

    company_name = "北京营力特建筑工程有限公司"
    project_name = project.get("name", "工程项目") if project else "通用工程项目"
    
    person_name = person.get("name", "未填写")
    id_number = person.get("id_number", "未填写")
    gender = person.get("gender", "男")
    phone = person.get("phone", "未填写")
    job_type = person.get("job_type", "施工人员")
    salary_type = person.get("salary_type", "日薪")
    salary_rate = person.get("salary_rate", 0.0)
    bank_name = person.get("bank_name", "中国工商银行")
    bank_card = person.get("bank_card", "未填写")
    address = person.get("address", "未填写")

    salary_str = f"{salary_rate:.1f} 元 / {salary_type}" if salary_rate else f"按约定按月/日结算 ({salary_type})"

    if template_id == "01_labor_contract":
        # 1-to-1 Replica of 公司官方《合同_谢瑞鸣.docx》
        body_content = f"""
        <div class="contract-doc">
            <div class="contract-header" style="text-align: center; margin-bottom: 30px;">
                <h2 style="font-size: 18px; color: #475569; margin-bottom: 4px; font-weight: normal;">劳务合同（不交社保版）</h2>
                <h1 style="font-size: 28px; color: #0f766e; margin-top: 0; letter-spacing: 4px;">劳 务 合 同</h1>
                <p style="font-size: 13px; color: #94a3b8;">合同编号：YLT-LW-{datetime.now().strftime('%Y%m%d%H%M%S')}</p>
            </div>

            <div class="party-info" style="font-size: 15px; line-height: 2.0; margin-bottom: 24px;">
                <p style="margin-bottom: 12px;"><strong>甲方（用工方）：</strong><u>{company_name}</u></p>
                <p style="margin-bottom: 8px;"><strong>乙方（提供劳务方）：</strong></p>
                <div style="margin-left: 20px; font-size: 14.5px; line-height: 1.9; background: #f8fafc; padding: 16px 20px; border-radius: 8px; border: 1px dashed #cbd5e1;">
                    <p style="margin: 4px 0;">姓名：<u>{person_name}</u></p>
                    <p style="margin: 4px 0;">性别：<u>{gender}</u></p>
                    <p style="margin: 4px 0;">居民身份证号码：<u class="font-mono">{id_number}</u></p>
                    <p style="margin: 4px 0;">住址/户籍地址：<u>{address}</u></p>
                    <p style="margin: 4px 0;">联系电话：<u>{phone}</u></p>
                </div>
            </div>

            <div class="contract-body" style="font-size: 15px; line-height: 1.9;">
                <p style="text-indent: 2em; margin-bottom: 16px;">鉴于乙方为灵活就业人员，双方经平等自愿协商，就乙方为甲方在 <strong>【{project_name}】</strong> 项目提供劳务一事达成如下协议：</p>

                <h3 style="font-size: 16.5px; color: #0f766e; margin-top: 24px; margin-bottom: 8px;">一、劳务内容</h3>
                <p style="text-indent: 2em; margin-top: 0;">乙方为甲方提供 <strong><u>{job_type}</u></strong> 服务，并遵守现场施工安全生产规范。</p>

                <h3 style="font-size: 16.5px; color: #0f766e; margin-top: 24px; margin-bottom: 8px;">二、劳务报酬</h3>
                <p style="text-indent: 2em; margin-top: 0; margin-bottom: 6px;">1. 甲方按月支付乙方劳务报酬 <strong><u>{salary_str}</u></strong>（税后）。</p>
                <p style="text-indent: 2em; margin-top: 0;">2. 劳务费用打款账户：<strong><u>{bank_name}（卡号: {bank_card}）</u></strong>。</p>

                <h3 style="font-size: 16.5px; color: #0f766e; margin-top: 24px; margin-bottom: 8px;">三、特别约定</h3>
                <p style="text-indent: 2em; margin: 4px 0;">1. <strong>双方不建立劳动关系，不缴纳社会保险。</strong></p>
                <p style="text-indent: 2em; margin: 4px 0;">2. 乙方自行承担个人所得税申报义务。</p>
                <p style="text-indent: 2em; margin: 4px 0;">3. 乙方在劳务过程中须做好个人安全防护，佩戴安全帽，严禁违章作业。</p>
            </div>

            <div class="signature-section" style="margin-top: 50px; padding-top: 30px; border-top: 2px dashed #0f766e; display: grid; grid-template-columns: 1fr 1fr; gap: 40px; font-size: 15px;">
                <div class="sig-box" style="position: relative;">
                    <p style="margin-bottom: 12px;"><strong>甲方（盖章）：</strong> <u>{company_name}</u></p>
                    <div style="height: 70px; margin: 12px 0; display: flex; align-items: center;">
                        <span style="border: 2px dashed #dc2626; color: #dc2626; padding: 8px 18px; border-radius: 6px; font-weight: bold; font-size: 13.5px; transform: rotate(-4deg); display: inline-block;">[ 公司公章 / 法人电子印章处 ]</span>
                    </div>
                    <p style="margin-top: 16px;">法定代表人（签字）：_________________</p>
                    <p style="margin-top: 12px;">日期：<u>{signing_date}</u></p>
                </div>
                <div class="sig-box">
                    <p style="margin-bottom: 12px;"><strong>乙方（签字）：</strong> <u>{person_name}</u></p>
                    <div style="height: 70px; margin: 12px 0; display: flex; align-items: center;">
                        <span style="color: #64748b; font-size: 14.5px;">手写签名/按手印：_________________</span>
                    </div>
                    <p style="margin-top: 16px;">居民身份证号：<u class="font-mono">{id_number}</u></p>
                    <p style="margin-top: 12px;">日期：<u>{signing_date}</u></p>
                </div>
            </div>
        </div>
        """
    else:
        # 其他用工协议模版
        body_content = f"""
        <div class="contract-doc">
            <div class="contract-header" style="text-align: center; margin-bottom: 30px;">
                <h1 style="font-size: 26px; color: #0f766e; margin-top: 0; letter-spacing: 2px;">{template_info['name']}</h1>
                <p style="font-size: 13px; color: #94a3b8;">合同编号：YLT-HT-{datetime.now().strftime('%Y%m%d%H%M%S')}</p>
            </div>

            <div class="party-info" style="font-size: 15px; line-height: 2.0; margin-bottom: 24px;">
                <p><strong>甲方（用工方/项目部）：</strong><u>{company_name}</u></p>
                <p><strong>工程项目：</strong><u>{project_name}</u></p>
                <p><strong>乙方（人员）：</strong><u>{person_name}</u>（身份证：<u class="font-mono">{id_number}</u>，电话：<u>{phone}</u>，住址：<u>{address}</u>）</p>
            </div>

            <div class="contract-body" style="font-size: 15px; line-height: 1.9;">
                <h3 style="font-size: 16.5px; color: #0f766e; margin-top: 20px;">一、工作岗位与内容</h3>
                <p style="text-indent: 2em;">乙方根据工程建设需要，在【{project_name}】从事【{job_type}】服务。</p>

                <h3 style="font-size: 16.5px; color: #0f766e; margin-top: 20px;">二、薪资标准与发放方式</h3>
                <p style="text-indent: 2em;">1. 报酬标准：<strong><u>{salary_str}</u></strong>。</p>
                <p style="text-indent: 2em;">2. 指定打款卡号：<strong><u>{bank_name} ({bank_card})</u></strong>。</p>

                <h3 style="font-size: 16.5px; color: #0f766e; margin-top: 20px;">三、安全生产与合规</h3>
                <p style="text-indent: 2em;">乙方须严格遵守施工现场安全管理规定，佩戴合格劳动防护用品，违章不作业。</p>
            </div>

            <div class="signature-section" style="margin-top: 50px; padding-top: 30px; border-top: 2px dashed #0f766e; display: grid; grid-template-columns: 1fr 1fr; gap: 40px; font-size: 15px;">
                <div class="sig-box">
                    <p><strong>甲方（盖章）：</strong> <u>{company_name}</u></p>
                    <p style="margin-top: 16px;">代表人（签字）：_________________</p>
                    <p style="margin-top: 12px;">日期：<u>{signing_date}</u></p>
                </div>
                <div class="sig-box">
                    <p><strong>乙方（签字）：</strong> <u>{person_name}</u></p>
                    <p style="margin-top: 16px;">手写签名：_________________</p>
                    <p style="margin-top: 12px;">日期：<u>{signing_date}</u></p>
                </div>
            </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{template_info['name']} - {person_name}</title>
    <style>
        body {{
            font-family: "PingFang SC", "Microsoft YaHei", "SimSun", sans-serif;
            color: #1e293b;
            line-height: 1.8;
            padding: 40px 60px;
            max-width: 820px;
            margin: 0 auto;
            background: #ffffff;
        }}
        u {{
            text-underline-offset: 4px;
            padding: 0 4px;
            font-weight: 600;
        }}
        .font-mono {{
            font-family: Monaco, Consolas, monospace;
        }}
        @media print {{
            body {{ padding: 0; margin: 0; }}
        }}
    </style>
</head>
<body>
    {body_content}
</body>
</html>"""
    return html
