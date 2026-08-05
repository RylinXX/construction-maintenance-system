from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime

# Standard Templates for Personnel & Project Contract Generation
TEMPLATES = [
    {
        "id": "01_no_social_security_labor_contract",
        "name": "2026新版劳务合同（不交社保标准 Word 模板）",
        "category": "人员合同",
        "description": "基于桌面 Word .docx 模板自动提取填充：乙方姓名、身份证号、电话、住址、工种岗位及薪资报酬。",
        "docx_template": "2026_labor_contract_no_social_security.docx"
    },
    {
        "id": "02_standard_labor_contract",
        "name": "建筑施工劳动合同书（全日制规范版）",
        "category": "人员合同",
        "description": "适用于全日制及常驻工人的规范劳动合同，包含劳动报酬、安全生产及权益保障条款。",
        "docx_template": None
    },
    {
        "id": "03_subcontract_agreement",
        "name": "工程施工劳务用工协议书",
        "category": "劳务合同",
        "description": "适用于班组及专业劳务人员项目包干或按日结算的施工用工协议。",
        "docx_template": None
    },
    {
        "id": "04_temporary_work_agreement",
        "name": "建筑工人临时用工协议",
        "category": "人员合同",
        "description": "适用于短期零工、临时调配人员的简易用工协议。",
        "docx_template": None
    },
    {
        "id": "05_machinery_lease_contract",
        "name": "工程机械设备租赁合同（带司机）",
        "category": "其它",
        "description": "适用于钩机、铲车、水车等机械设备及其操作司机的机械租赁合同。",
        "docx_template": None
    }
]

def list_contract_templates():
    return TEMPLATES

def get_template_by_id(template_id: str):
    for t in TEMPLATES:
        if t["id"] == template_id:
            return t
    return TEMPLATES[0]

def fill_docx_template(dest_docx_path: Path, person: dict, project: dict | None, signing_date: str, contract_no: str):
    """Fill the real Word (.docx) document template with person and contract data."""
    try:
        import docx
        base_docx = Path(__file__).parent.parent / "templates" / "docx_templates" / "2026_labor_contract_no_social_security.docx"
        if not base_docx.exists():
            return
        doc = docx.Document(base_docx)
        
        person_name = person.get("name", "未填写")
        id_number = person.get("id_number", "未填写")
        phone = person.get("phone", "未填写")
        job_type = person.get("job_type", "施工人员")
        salary_type = person.get("salary_type", "日薪")
        salary_rate = person.get("salary_rate", 0.0)
        salary_str = f"{salary_rate:.1f}元/{salary_type}"
        address = person.get("address", "未填写")
        company_name = "北京营力特建筑工程有限公司"

        for p in doc.paragraphs:
            text = p.text
            if '合同编号:' in text:
                p.text = f'                                       合同编号: {contract_no}'
            elif '甲方 (用人单位)：' in text:
                p.text = f'甲方 (用人单位)： {company_name}'
            elif '乙方 (劳动者)  ：' in text:
                p.text = f'乙方 (劳动者)  ： {person_name}'
            elif '单位名称:' in text:
                p.text = f'单位名称: {company_name}'
            elif '地址:' in text:
                p.text = f'地址: 北京市门头沟区妙峰山镇水丁路1号院A074室'
            elif '姓名:' in text and '联系电话:' in text:
                p.text = f'姓名: {person_name}                                   联系电话: {phone}'
            elif '身份证号码:' in text:
                p.text = f'身份证号码: {id_number}                    紧急联系人电话: {phone}'
            elif '户籍所在地:' in text:
                p.text = f'户籍所在地: {address}'
            elif '住址:' in text:
                p.text = f'住址: {address}'
            elif '雇佣乙方为' in text:
                p.text = f'鉴于甲方业务发展需要，雇佣乙方为 {job_type} 提供劳务服务，经双方协商订立正式《劳务雇佣合同书》如下:'
            elif '乙方的劳动报酬为:' in text:
                p.text = f'2、甲乙双方约定，乙方的劳动报酬为: {salary_str}，劳务报酬发放日期为每月的 25 日，如遇发放日为节假日，甲方将顺延到最接近的一个工作日发放。'
            elif '签 订 时 间' in text:
                p.text = f'签 订 时 间   :  {signing_date}'

        dest_docx_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(dest_docx_path)
    except Exception as exc:
        print(f"Error filling docx template: {exc}")

def render_contract_html(template_id: str, person: dict, project: dict | None = None, signing_date: str = None) -> str:
    template_info = get_template_by_id(template_id)
    if not signing_date:
        signing_date = datetime.now().strftime("%Y年%m月%d日")

    company_name = "北京营力特建筑工程有限公司"
    project_name = project.get("name") if project else "个人通用/全公司人员调度"
    
    person_name = person.get("name", "未填写")
    id_number = person.get("id_number", "未填写")
    phone = person.get("phone", "未填写")
    job_type = person.get("job_type", "施工人员")
    salary_type = person.get("salary_type", "日薪")
    salary_rate = person.get("salary_rate", 0.0)
    bank_name = person.get("bank_name", "中国工商银行")
    bank_card = person.get("bank_card", "未填写")
    address = person.get("address", "未填写")

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
        <p>合同编号：YLT-CON-{datetime.now().strftime('%Y%m%d%H%M%S')}</p>
    </div>

    <div class="party-box">
        <div class="party-item"><label>甲方（用人单位）：</label><span>{company_name}</span></div>
        <div class="party-item"><label>项目/归属：</label><span>{project_name}</span></div>
        <div class="party-item"><label>乙方（劳动者）：</label><span>{person_name}</span></div>
        <div class="party-item"><label>身份证号码：</label><span>{id_number}</span></div>
        <div class="party-item"><label>联系电话：</label><span>{phone}</span></div>
        <div class="party-item"><label>工作岗位/工种：</label><span>{job_type}</span></div>
        <div class="party-item"><label>薪资标准：</label><span>{salary_str}</span></div>
        <div class="party-item"><label>户籍住址：</label><span>{address}</span></div>
    </div>

    <div class="contract-section">
        <h3>第一条 劳务用工约定</h3>
        <p>1. 乙方同意根据甲方工作安排，从事 <strong>{job_type}</strong> 岗位劳务服务工作。</p>
        <p>2. 乙方应遵守各项安全生产制度与规章，尽职尽责完成工作需要。</p>
    </div>

    <div class="contract-section">
        <h3>第二条 劳务报酬与保险约定</h3>
        <p>1. 双方约定劳务报酬标准为：<strong>{salary_str}</strong>。</p>
        <p>2. 乙方作为劳务人员，甲方支付给乙方的劳务报酬已包含各项补贴与相关社会保险费用，不再额外支付任何社会保险费用。乙方个人社会保障由乙方自行缴纳。</p>
    </div>

    <div class="contract-section">
        <h3>第三条 安全生产与解约条款</h3>
        <p>1. 任何一方均有权提前通知解除本合同，解除本合同不需支付经济补偿金。</p>
        <p>2. 如乙方自身身体原因发生意外的，所有责任由乙方自行承担，甲方及时组织送医协助。</p>
    </div>

    <div class="signature-box">
        <div class="sig-col">
            <h4>甲方（用人单位盖章/签字）：</h4>
            <div class="sig-line">代表人：________________</div>
            <div class="sig-line">签订日期：{signing_date}</div>
        </div>
        <div class="sig-col">
            <h4>乙方（劳动者签字/手印）：</h4>
            <div class="sig-line">乙方签名：<strong>{person_name}</strong></div>
            <div class="sig-line">签订日期：{signing_date}</div>
        </div>
    </div>
</body>
</html>"""
    return html
