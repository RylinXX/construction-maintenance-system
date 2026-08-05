from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime

# Standard HTML Templates for Contract Generation
TEMPLATES = [
    {
        "id": "01_labor_contract",
        "name": "建筑施工劳动合同书（标准版）",
        "category": "人员合同",
        "description": "适用于全日制及项目常驻工人的规范劳动合同，包含劳动报酬、安全生产及权益保障条款。",
        "template_filename": "01_labor_contract.html"
    },
    {
        "id": "02_subcontract_agreement",
        "name": "工程施工劳务用工协议书",
        "category": "劳务合同",
        "description": "适用于班组及专业劳务人员项目包干或按日结算的施工用工协议。",
        "template_filename": "02_subcontract_agreement.html"
    },
    {
        "id": "03_temporary_work_agreement",
        "name": "建筑工人临时用工协议",
        "category": "人员合同",
        "description": "适用于短期零工、临时调配人员的简易用工协议。",
        "template_filename": "03_temporary_work_agreement.html"
    },
    {
        "id": "04_machinery_lease_contract",
        "name": "工程机械设备租赁合同（带司机）",
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

    company_name = "营力特建筑工程有限公司"
    project_name = project.get("name", "工程项目") if project else "通用工程项目"
    
    person_name = person.get("name", "未填写")
    id_number = person.get("id_number", "未填写")
    phone = person.get("phone", "未填写")
    job_type = person.get("job_type", "施工人员")
    salary_type = person.get("salary_type", "日薪")
    salary_rate = person.get("salary_rate", 0.0)
    bank_name = person.get("bank_name", "中国工商银行")
    bank_card = person.get("bank_card", "未填写")
    address = person.get("address", "北京市海湾区建设基地")

    salary_str = f"{salary_rate:.1f} 元 / {salary_type}"

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
            max-width: 850px;
            margin: 0 auto;
            background: #ffffff;
        }}
        .contract-header {{
            text-align: center;
            border-bottom: 2px solid #0f766e;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .contract-header h1 {{
            font-size: 24px;
            color: #0f766e;
            margin: 0 0 8px 0;
            letter-spacing: 1px;
        }}
        .contract-header p {{
            font-size: 13px;
            color: #64748b;
            margin: 0;
        }}
        .party-box {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px 24px;
            margin-bottom: 30px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }}
        .party-item {{
            font-size: 14px;
        }}
        .party-item label {{
            color: #64748b;
            font-weight: 600;
        }}
        .party-item span {{
            color: #0f172a;
            font-weight: 700;
            border-bottom: 1px dashed #94a3b8;
            padding: 0 4px;
        }}
        .contract-section {{
            margin-bottom: 24px;
        }}
        .contract-section h3 {{
            font-size: 16px;
            color: #0f766e;
            border-left: 4px solid #0f766e;
            padding-left: 10px;
            margin-bottom: 12px;
        }}
        .contract-section p, .contract-section li {{
            font-size: 14px;
            color: #334155;
            text-align: justify;
        }}
        .signature-box {{
            margin-top: 50px;
            padding-top: 30px;
            border-top: 1px solid #cbd5e1;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
        }}
        .sig-col h4 {{
            font-size: 15px;
            margin-bottom: 40px;
            color: #1e293b;
        }}
        .sig-line {{
            font-size: 14px;
            color: #64748b;
            margin-bottom: 12px;
        }}
        .stamp-badge {{
            display: inline-block;
            border: 2px dashed #ef4444;
            color: #ef4444;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            transform: rotate(-5deg);
        }}
        @media print {{
            body {{ padding: 0; margin: 0; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="contract-header">
        <h1>{template_info['name']}</h1>
        <p>编号：YLT-CON-{datetime.now().strftime('%Y%m%d%H%M%S')}</p>
    </div>

    <div class="party-box">
        <div class="party-item"><label>甲方（用人单位/项目部）：</label><span>{company_name}</span></div>
        <div class="party-item"><label>归属工程项目：</label><span>{project_name}</span></div>
        <div class="party-item"><label>乙方（劳动者/人员）：</label><span>{person_name}</span></div>
        <div class="party-item"><label>身份证号码：</label><span>{id_number}</span></div>
        <div class="party-item"><label>联系电话：</label><span>{phone}</span></div>
        <div class="party-item"><label>工作岗位/工种：</label><span>{job_type}</span></div>
        <div class="party-item"><label>薪资标准与结算：</label><span>{salary_str}</span></div>
        <div class="party-item"><label>指定收款银行卡：</label><span>{bank_name} ({bank_card})</span></div>
    </div>

    <div class="contract-section">
        <h3>第一条 工作内容与工作地点</h3>
        <p>1. 乙方同意根据甲方工作需要，在 <strong>{project_name}</strong> 现场从事 <strong>{job_type}</strong> 岗位工作。</p>
        <p>2. 乙方应严格遵守现场安全生产规章制度，服从现场施工管理人员的合理调度与安排。</p>
    </div>

    <div class="contract-section">
        <h3>第二条 劳动报酬与支付方式</h3>
        <p>1. 双方约定劳报酬结算标准为：<strong>{salary_str}</strong>。</p>
        <p>2. 结算周期：甲方按月根据考勤打卡记录核算工资，打款至乙方指定银行账户：<strong>{bank_name} ({bank_card})</strong>。</p>
    </div>

    <div class="contract-section">
        <h3>第三条 安全生产与权益保障</h3>
        <p>1. 甲方依法为乙方提供符合国家标准的劳动安全卫生条件和必要的劳动防护用品。</p>
        <p>2. 乙方入场前须接受三级安全教育培训，遵守安全操作规程，严禁违章作业。</p>
    </div>

    <div class="contract-section">
        <h3>第四条 协议期限与终止</h3>
        <p>本协议自双方签字/盖章之日起生效，至 <strong>{project_name}</strong> 项目相关工种作业完工结清薪资后自动终止。</p>
    </div>

    <div class="signature-box">
        <div class="sig-col">
            <h4>甲方（盖章/签字）：</h4>
            <div class="sig-line">代表人（签字）：________________</div>
            <div class="sig-line">签署日期：{signing_date}</div>
        </div>
        <div class="sig-col">
            <h4>乙方（签字/手印）：</h4>
            <div class="sig-line">乙方签名：<strong>{person_name}</strong></div>
            <div class="sig-line">签署日期：{signing_date}</div>
        </div>
    </div>
</body>
</html>"""
    return html
