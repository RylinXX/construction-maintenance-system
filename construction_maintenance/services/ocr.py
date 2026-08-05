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
                data={"message": "未配置 AI 模型 API Key，请在系统设置中配置后再试"},
                confidence=None,
            )

        image_payload_items: list[dict[str, Any]] = [
            {"type": "text", "text": _prompt_for_item_type(item_type)}
        ]

        try:
            import fitz

            with fitz.open(path) as doc:
                if len(doc) == 0:
                    raise ValueError("文件内容为空")

                # 支持多页 PDF（如正反面在两页 PDF 中），渲染前 2 页
                pages_to_render = [doc[0]]
                if len(doc) > 1:
                    pages_to_render.append(doc[1])

                for page in pages_to_render:
                    max_side = max(page.rect.width, page.rect.height)
                    is_pdf = path.suffix.lower() == ".pdf"
                    scale = 1600 / max_side if is_pdf or max_side > 1600 else 1.0
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
                    img_bytes = pix.tobytes("png")
                    image_data = base64.b64encode(img_bytes).decode("ascii")
                    image_payload_items.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"},
                        }
                    )
        except Exception as exc:
            if path.suffix.lower() == ".pdf":
                return BatchOcrResult(
                    status="待确认",
                    data={"message": f"PDF 解析或渲染失败，请人工确认：{exc}"},
                    confidence=None,
                )
            try:
                mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
                image_data = base64.b64encode(path.read_bytes()).decode("ascii")
                image_payload_items.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                    }
                )
            except Exception as read_exc:
                return BatchOcrResult(
                    status="待确认",
                    data={"message": f"加载文件失败，请人工确认：{read_exc}"},
                    confidence=None,
                )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": image_payload_items,
                }
            ],
            "temperature": 0,
        }

        endpoint_url = self.base_url
        if not endpoint_url.endswith("/chat/completions"):
            endpoint_url = f"{endpoint_url}/chat/completions"

        request = urllib.request.Request(
            endpoint_url,
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
            if item_type == "person":
                parsed = _post_process_person_data(parsed)
        except (KeyError, OSError, urllib.error.HTTPError, json.JSONDecodeError, ValueError) as exc:
            return BatchOcrResult(
                status="待确认",
                data={"message": f"AI OCR 识别失败，请人工确认：{exc}"},
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
    suffix = path.suffix.lower()
    if suffix not in IMAGE_SUFFIXES and suffix != ".pdf":
        return BatchOcrResult(
            status="待确认",
            data={"message": UnsupportedFileType.message},
            confidence=None,
        )

    if recognizer is None:
        base_url = current_app.config.get("ARK_BASE_URL", "")
        model = current_app.config.get("ARK_MODEL", "")
        api_key = current_app.config.get("ARK_API_KEY", "")

        try:
            from construction_maintenance import repositories as repo

            s = repo.get_system_settings()
            provider = s.get("active_ai_provider", "ali_bailian")
            model_setting = s.get("active_ai_model") or "qwen3.5-plus"

            if provider == "ali_bailian":
                s_url = s.get("ali_bailian_base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
                s_key = s.get("ali_bailian_api_key") or ""
            elif provider == "deepseek":
                s_url = s.get("deepseek_base_url") or "https://api.deepseek.com"
                s_key = s.get("deepseek_api_key") or ""
            else:  # bytedance_ark
                s_url = s.get("bytedance_ark_base_url") or "https://ark.cn-beijing.volces.com/api/v3"
                s_key = s.get("bytedance_ark_api_key") or ""

            if s_key:
                base_url = s_url
                model = model_setting
                api_key = s_key
        except Exception:
            pass

        recognizer = ArkOcrRecognizer(
            base_url=base_url,
            model=model,
            api_key=api_key,
        )
    return recognizer.recognize_image(path, item_type)


def validate_id_card_checksum(id_number: str) -> bool:
    """Validate 18-digit Chinese Resident ID card number using ISO 7064:1983.MOD 11-2 algorithm."""
    id_str = str(id_number or "").strip().upper()
    if len(id_str) != 18 or not id_str[:17].isdigit():
        return False
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_codes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']
    total = sum(int(id_str[i]) * weights[i] for i in range(17))
    return check_codes[total % 11] == id_str[17]


def _prompt_for_item_type(item_type: str) -> str:
    if item_type == "person":
        return (
            "你是一个高精度中国居民身份证结构化数据 OCR 识别接口。"
            "请读取图片中的身份证（含正面人像面、反面国徽面或双面拼图），严格输出符合以下规范的 JSON 对象：\n"
            "{\n"
            '  "name": "姓名（若未找到返回 null）",\n'
            '  "gender": "性别（必须为 男 或 女，若未找到返回 null）",\n'
            '  "ethnicity": "民族（如 汉，若未找到返回 null）",\n'
            '  "birth_date": "出生日期（YYYY-MM-DD，若未找到返回 null）",\n'
            '  "address": "身份证住址完整文本（若未找到返回 null）",\n'
            '  "id_number": "18位公民身份号码（包含大写 X，若未找到返回 null）",\n'
            '  "issuing_authority": "签发机关（国徽面上的签发机关，若未找到返回 null）",\n'
            '  "valid_from": "有效期限起始日期（YYYY-MM-DD，若未找到返回 null）",\n'
            '  "valid_until": "有效期限截止日期（YYYY-MM-DD，若是长期有效请填 长期，若未找到返回 null）",\n'
            '  "is_long_term": false,\n'
            '  "confidence": {\n'
            '    "name": 0.99,\n'
            '    "id_number": 0.98,\n'
            '    "address": 0.92\n'
            '  }\n'
            "}\n"
            "【严禁事项】：未识别到的字段必须返回 null，绝对禁止猜测、虚构、推测或编写任何自然语言合同正文！"
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


def mask_id_number(id_num: str) -> str:
    """Mask ID card number for privacy security in logs."""
    s = str(id_num or "").strip()
    if len(s) == 18:
        return f"{s[:6]}********{s[14:]}"
    return s


def _post_process_person_data(parsed: dict[str, Any]) -> dict[str, Any]:
    fields = ["name", "gender", "ethnicity", "birth_date", "address", "id_number", "issuing_authority", "valid_from", "valid_until"]
    for f in fields:
        val = parsed.get(f)
        if val in ("", "null", "None", None):
            parsed[f] = None

    id_num = str(parsed.get("id_number") or "").strip().replace(" ", "").replace("-", "").upper()
    if id_num:
        parsed["id_number"] = id_num
        parsed["id_checksum_valid"] = validate_id_card_checksum(id_num)
        if len(id_num) == 18 and id_num[:17].isdigit():
            year = id_num[6:10]
            month = id_num[10:12]
            day = id_num[12:14]
            try:
                y, m, d = int(year), int(month), int(day)
                if 1920 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31:
                    derived_date = f"{year}-{month:02d}-{day:02d}"
                    if not parsed.get("birth_date"):
                        parsed["birth_date"] = derived_date
                if not parsed.get("gender"):
                    parsed["gender"] = "男" if int(id_num[16]) % 2 == 1 else "女"
            except Exception:
                pass

    # Confidence dictionary
    if not isinstance(parsed.get("confidence"), dict):
        c_val = _normalize_confidence(parsed.get("confidence")) or 0.95
        parsed["confidence"] = {
            "name": c_val,
            "id_number": c_val,
            "address": c_val,
        }

    return parsed


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
