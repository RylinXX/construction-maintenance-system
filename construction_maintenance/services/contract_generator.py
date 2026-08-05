from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime

# Standard HTML Templates for Contract Generation
TEMPLATES = [
    {
        "id": "01_labor_contract",
        "name": "2026新版《劳务合同》（不交社保官方版）",
        "category": "人员合同",
        "description": "基于桌面《2026新版劳务合同（不交社保）.docx》官方规范研制，包含完整六大章节条款、包含社保费用申明、解约与保密承诺及印章栏。",
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
    company_address = "北京市门头沟区妙峰山镇水丁路1号院"
    project_name = project.get("name", "通用工程项目") if project else "通用工程项目"
    
    person_name = person.get("name", "未填写")
    id_number = person.get("id_number", "未填写")
    phone = person.get("phone", "未填写")
    emergency_phone = person.get("emergency_phone") or phone
    job_type = person.get("job_type", "施工人员")
    salary_type = person.get("salary_type", "日薪")
    salary_rate = person.get("salary_rate", 0.0)
    bank_name = person.get("bank_name", "中国工商银行")
    bank_card = person.get("bank_card", "未填写")
    address = person.get("address", "未填写")
    entry_date = person.get("entry_date") or datetime.now().strftime("%Y-%m-%d")

    salary_str = f"每月 {salary_rate:.1f} 元 ({salary_type})" if salary_rate else f"按约定按月结算 ({salary_type})"

    if template_id == "01_labor_contract":
        # 100% Word-for-Word Replica of Desktop: 2026新版劳务合同（不交社保）.docx
        body_content = f"""
        <div class="contract-doc">
            <div class="contract-header" style="text-align: center; margin-bottom: 24px; border-bottom: 2px solid #0f766e; padding-bottom: 16px;">
                <h1 style="font-size: 28px; color: #0f766e; margin: 0 0 6px 0; letter-spacing: 6px;">劳 务 合 同</h1>
                <p style="font-size: 13px; color: #64748b; margin: 0;">合同编号：YLT-2026-LW-{datetime.now().strftime('%Y%m%d%H%M%S')}</p>
            </div>

            <!-- Party Table Info Box -->
            <div class="party-table" style="margin-bottom: 24px;">
                <table style="width: 100%; border-collapse: collapse; border: 1.5px solid #0f766e; font-size: 14px;">
                    <tr style="background: #f0fdf4;">
                        <th colspan="2" style="border: 1px solid #99f6e4; padding: 8px 12px; text-align: left; color: #0f766e; font-size: 15px;">用工方 ( 甲方 )</th>
                        <th colspan="2" style="border: 1px solid #99f6e4; padding: 8px 12px; text-align: left; color: #0f766e; font-size: 15px;">劳务方 ( 乙方 )</th>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px; font-weight: bold; width: 15%; background: #fafafa;">单位名称</td>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px; width: 35%;"><u>{company_name}</u></td>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px; font-weight: bold; width: 15%; background: #fafafa;">姓名</td>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px; width: 35%;"><u>{person_name}</u></td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px; font-weight: bold; background: #fafafa;">单位地址</td>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px;"><u>{company_address}</u></td>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px; font-weight: bold; background: #fafafa;">联系电话</td>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px;"><u>{phone}</u></td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px; font-weight: bold; background: #fafafa;">归属项目</td>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px;"><u>{project_name}</u></td>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px; font-weight: bold; background: #fafafa;">身份证号码</td>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px;" class="font-mono"><u>{id_number}</u></td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px; font-weight: bold; background: #fafafa;">户籍所在地</td>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px;"><u>{address}</u></td>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px; font-weight: bold; background: #fafafa;">紧急联系电话</td>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px;"><u>{emergency_phone}</u></td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #cbd5e1; padding: 8px 12px; font-weight: bold; background: #fafafa;">现居住地址</td>
                        <td colspan="3" style="border: 1px solid #cbd5e1; padding: 8px 12px;"><u>{address}</u></td>
                    </tr>
                </table>
            </div>

            <div class="contract-body" style="font-size: 14.5px; line-height: 1.85; color: #1e293b;">
                <p style="text-indent: 2em; margin-bottom: 16px;">
                    鉴于甲方业务发展需要，雇佣乙方为 <strong><u>【{project_name}】</u></strong> 提供 <strong><u>{job_type}</u></strong> 劳务服务，经双方协商订立正式《劳务雇佣合同书》如下：
                </p>

                <h3 style="font-size: 16px; color: #0f766e; margin-top: 20px; margin-bottom: 8px;">一、合同期限</h3>
                <p style="text-indent: 2em; margin: 4px 0;">
                    1、本合同期限自 <strong><u>{entry_date}</u></strong> 起至 <strong><u>项目完工及劳务费用总结清日</u></strong> 止；
                </p>
                <p style="text-indent: 2em; margin: 4px 0;">
                    2、如双方需要，可在合同期满前 1 个月协商续签劳务雇佣合同。如合同期已满，双方未续签合同，但乙方从事的有关工作尚未结束，则合同应顺延至有关业务结束。
                </p>

                <h3 style="font-size: 16px; color: #0f766e; margin-top: 20px; margin-bottom: 8px;">二、劳务内容</h3>
                <p style="text-indent: 2em; margin: 4px 0;">
                    乙方承担的劳务内容为：<strong><u>{job_type} 岗位施工及现场劳务服务</u></strong>。
                </p>

                <h3 style="font-size: 16px; color: #0f766e; margin-top: 20px; margin-bottom: 8px;">三、劳务要求</h3>
                <p style="text-indent: 2em; margin: 3px 0;">1、爱护甲方财物，保守甲方机密，维护甲方利益，服从甲方的管理。</p>
                <p style="text-indent: 2em; margin: 3px 0;">2、因乙方过失给甲方造成经济损失的，甲方有权要求乙方承担赔偿责任。</p>
                <p style="text-indent: 2em; margin: 3px 0;">3、乙方应严格遵守国家各项法律规定。</p>
                <p style="text-indent: 2em; margin: 3px 0;">4、乙方应遵守甲方制定的工作规范和各项规章制度，尽职尽责做好工作。</p>
                <p style="text-indent: 2em; margin: 3px 0;">5、如由于工作需要，甲方在要求乙方加班时，在无特殊原因的情况下，乙方必须配合。</p>
                <p style="text-indent: 2em; margin: 3px 0;">6、乙方应严格遵守本合同的附加条款。</p>

                <h3 style="font-size: 16px; color: #0f766e; margin-top: 20px; margin-bottom: 8px;">四、劳务时间、劳务报酬及福利</h3>
                <p style="text-indent: 2em; margin: 3px 0;">1、甲方根据国家规定和工作的需要，合理安排乙方工作时间，乙方应服从统一安排，不得以种种理由推脱，否则甲方有权视情节轻重程度给予处罚或解除劳务合同。甲方在劳务关系建立的同时告知乙方应遵守的各项规章制度。</p>
                <p style="text-indent: 2em; margin: 3px 0;">2、甲乙双方约定，乙方的劳动报酬为：<strong><u>{salary_str}</u></strong>，劳务报酬发放日期为每月的 <strong><u>25 日</u></strong>，如遇发放日为节假日，甲方将顺延到最接近的一个工作日发放。指定收款银行账户：<strong><u>{bank_name} (卡号: {bank_card})</u></strong>。</p>
                <p style="text-indent: 2em; margin: 3px 0;">3、乙方在正常出勤并付出正常劳务后，有权获得相应劳务报酬。</p>
                <p style="text-indent: 2em; margin: 3px 0; background: #fff7ed; padding: 6px 10px; border-left: 4px solid #f97316;">
                    4、<strong>乙方作为劳务人员，甲方支付给乙方的工资已包含各种社会保险费用，不再额外支付乙方的任何社会保险费用。乙方个人社会养老保险金由乙方自行缴纳。</strong>
                </p>

                <h3 style="font-size: 16px; color: #0f766e; margin-top: 20px; margin-bottom: 8px;">五、协议的解除与终止</h3>
                <p style="text-indent: 2em; margin: 3px 0;">1、在本合同期限内，任何一方均有权提前 30 天通知对方解除本合同，解除本合同不需支付经济补偿金。</p>
                <p style="text-indent: 2em; margin: 3px 0;">2、甲方因乙方不能胜任工作或有违法违纪行为，甲方可随时与乙方解除本合同，不需要提前通知乙方。</p>
                <p style="text-indent: 2em; margin: 3px 0;">3、在没有特殊情况的前提下，若甲方未能按照本合同的约定提供劳务报酬，经乙方书面催告后 7 日内仍未支付的，乙方可以随时解除本合同，不受提前通知的限制。</p>
                <p style="text-indent: 2em; margin: 3px 0;">4、本合同到期或过期，如双方未答复，自行终止本合同，不需要提前通知。</p>
                <p style="text-indent: 2em; margin: 3px 0;">5、甲乙双方无论因何原因解除或终止本合同，乙方应在 3 日内办理工作交接归还甲方财物等解约手续。如离职时未办理财物交接手续，甲方有权在不违反有关法律法规规定的前提下，扣除乙方相等的劳务报酬。</p>

                <h3 style="font-size: 16px; color: #0f766e; margin-top: 20px; margin-bottom: 8px;">六、其它</h3>
                <p style="text-indent: 2em; margin: 3px 0;">1、乙方承诺：乙方与甲方建立劳务关系完全是真实、自由的意愿，且不会让任何第三方就甲乙双方的劳务关系对甲方进行法律申诉。</p>
                <p style="text-indent: 2em; margin: 3px 0;">2、乙方承诺：在用工期限内及解除劳务合同后 2 年内，乙方不得向任何第三方透露甲方客户信息，包括但不仅限于经营管理信息，项目内容及各项数据信息等。否则乙方应赔偿甲方因此而造成的全部损失。</p>
                <p style="text-indent: 2em; margin: 3px 0;">3、如乙方自身身体原因，在上下班期间发生意外的，所有的责任均由乙方自行承担，甲方不承担由此发生的一切责任，但是甲方必须及时组织实施施救、送医等措施。</p>
                <p style="text-indent: 2em; margin: 3px 0;">4、本合同自双方签订之日起，任何一方不得擅自修改或变更，合同履行中如有未尽事宜，经双方协商另行补充，与本合同具有同等效力。</p>
                <p style="text-indent: 2em; margin: 3px 0;">5、双方如因履行合同发生争议，应首先友好协商解决。协商不成，任何一方都有权向甲方所在地人民法院提起诉讼。</p>
            </div>

            <!-- Signature Box -->
            <div class="signature-section" style="margin-top: 40px; padding-top: 24px; border-top: 2px dashed #0f766e; display: grid; grid-template-columns: 1fr 1fr; gap: 40px; font-size: 14.5px;">
                <div class="sig-box">
                    <p style="margin-bottom: 10px;"><strong>甲方 (盖章)：</strong> <u>{company_name}</u></p>
                    <div style="height: 70px; margin: 10px 0; display: flex; align-items: center;">
                        <span style="border: 2px dashed #dc2626; color: #dc2626; padding: 8px 18px; border-radius: 6px; font-weight: bold; font-size: 13.5px; transform: rotate(-4deg); display: inline-block;">[ 公司公章 / 法人电子盖章处 ]</span>
                    </div>
                    <p style="margin: 6px 0;">法定代表人：_________________</p>
                    <p style="margin: 6px 0;">签订日期：<u>{signing_date}</u></p>
                </div>
                <div class="sig-box">
                    <p style="margin-bottom: 10px;"><strong>乙方 (签字/盖章)：</strong> <u>{person_name}</u></p>
                    <div style="height: 70px; margin: 10px 0; display: flex; align-items: center;">
                        <span style="color: #64748b; font-size: 14px;">手写签名 / 按手印处：_________________</span>
                    </div>
                    <p style="margin: 6px 0;">身份证号码：<u class="font-mono">{id_number}</u></p>
                    <p style="margin: 6px 0;">签订日期：<u>{signing_date}</u></p>
                </div>
            </div>

            <!-- Supplement Box -->
            <div style="margin-top: 30px; border-top: 1px solid #cbd5e1; padding-top: 16px;">
                <h4 style="font-size: 15px; color: #0f766e; margin: 0 0 8px 0;">补充条款</h4>
                <p style="font-size: 13.5px; color: #64748b; margin-bottom: 40px;">经甲乙双方协商一致，对本合同做以下补充说明：_____________________________________________________</p>
            </div>

            <!-- Attachment Area -->
            <div style="margin-top: 20px; border: 1.5px dashed #94a3b8; padding: 20px; border-radius: 8px; text-align: center; background: #fafafa;">
                <span style="font-size: 13px; color: #64748b; font-weight: bold;">【 粘贴附件区域 】：乙方身份证正反面复印件或其他证明文件粘贴栏</span>
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
