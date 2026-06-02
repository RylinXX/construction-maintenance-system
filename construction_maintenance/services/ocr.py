from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import current_app


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass(frozen=True)
class BatchOcrResult:
    status: str
    data: dict[str, Any]
    confidence: float | None = None


class UnsupportedFileType:
    message = "暂不支持自动识别 PDF，请人工确认"


class ArkOcrRecognizer:
    def __init__(self, *, base_url: str, model: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    def recognize_image(self, path: Path, item_type: str) -> BatchOcrResult:
        if not self.api_key:
            return BatchOcrResult(
                status="待确认",
                data={"message": "未配置火山引擎 API Key，请人工确认"},
                confidence=None,
            )

        mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        image_data = base64.b64encode(path.read_bytes()).decode("ascii")
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _prompt_for_item_type(item_type)},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                        },
                    ],
                }
            ],
            "temperature": 0,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            parsed = _parse_model_json(content)
        except (KeyError, OSError, urllib.error.HTTPError, json.JSONDecodeError, ValueError) as exc:
            return BatchOcrResult(
                status="待确认",
                data={"message": f"OCR 识别失败，请人工确认：{exc}"},
                confidence=None,
            )

        return BatchOcrResult(
            status="已识别",
            data=parsed,
            confidence=_normalize_confidence(parsed.get("confidence")),
        )


def recognize_batch_upload(
    path: Path,
    item_type: str,
    recognizer: ArkOcrRecognizer | None = None,
) -> BatchOcrResult:
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        return BatchOcrResult(
            status="待确认",
            data={"message": UnsupportedFileType.message},
            confidence=None,
        )

    if recognizer is None:
        recognizer = ArkOcrRecognizer(
            base_url=current_app.config["ARK_BASE_URL"],
            model=current_app.config["ARK_MODEL"],
            api_key=current_app.config["ARK_API_KEY"],
        )
    return recognizer.recognize_image(path, item_type)


def _prompt_for_item_type(item_type: str) -> str:
    if item_type == "person":
        return (
            "请识别图片中的员工身份证或人员资料，严格返回 JSON，不要输出解释。"
            "字段包括：name,id_number,gender,birth_date,address,confidence,notes。"
            "无法识别的字段用空字符串.confidence 使用 0 到 1 的数字。"
        )
    if item_type == "qualification":
        return (
            "请识别图片中的企业资质证书、证照或营业执照，进行AI辅助信息提取，并严格返回 JSON，不要输出任何额外的解释。"
            "返回的 JSON 字段必须包括：company_name, name_select, certificate_no, credit_code, legal_person, phone, issue_date, expiry_date, is_long_term, notes, confidence。"
            "注意细节要求："
            "1. company_name 为证书上的企业/公司名称或单位名称。"
            "2. name_select 为资质证照类型，必须只能是以下值之一：'营业执照', '开户证明', '开票信息', '建筑资质', '安全生产资质', '八大员人员证书', '法人身份证'。如果都不符合上述类型，请返回 'CUSTOM'。"
            "3. certificate_no 为证书编号或证照号码（例如营业执照的统一社会信用代码，或者资质证书编号）。"
            "4. credit_code 为统一社会信用代码（通常在营业执照或开票信息中，如果是其他资质证书则留空）。"
            "5. legal_person 为法定代表人姓名。"
            "6. phone 为联系电话。"
            "7. issue_date 必须转换为标准的 YYYY-MM-DD 格式（例如 '2026-05-30'），无法识别的用空字符串。"
            "8. expiry_date 必须转换为标准的 YYYY-MM-DD 格式，如果是长期有效，请留空。"
            "9. is_long_term 为布尔值 (true 或 false)，代表是否长期有效。"
            "10. notes 为核准范围、备注说明或详细的资质名称等信息（例如：如果是 CUSTOM，可以在 notes 中指明真实的资质证照名称）。"
            "11. confidence 为置信度，使用 0 到 1 之间的数值。"
        )
    return (
        "请识别图片中的工程费用凭证或发票，进行AI辅助信息提取，并严格返回 JSON，不要输出任何额外的解释。"
        "返回的 JSON 字段必须包括：voucher_date, voucher_type, amount, payment_method, notes, confidence。"
        "注意细节要求："
        "1. voucher_date 必须转换为标准的 YYYY-MM-DD 格式（例如 '2026-05-30'）。如果无法确定年份，默认使用今年 2026 年。"
        "2. amount 必须为纯数字或浮点数，代表凭证的总支出金额。"
        "3. payment_method 为付款方式，例如 '微信零钱', '微信转账', '支付宝', '现金', '建设银行储蓄卡(5567)' 等。"
        "4. notes 为凭证上的备注、购买内容或交易对手，如 '购买五金'、'加柴油' 等。"
        "5. voucher_type 尽量归类为：材料费用、油费、电费、人工工资、员工报销、其它。请不要将'转账凭证'归为费用分类。"
        "6. confidence 为置信度，使用 0 到 1 之间的数值。"
    )


def _parse_model_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("OCR 结果不是对象")
    return parsed


def _normalize_confidence(value: Any) -> float | None:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, confidence))
