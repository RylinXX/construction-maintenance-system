from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
import math
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook

from construction_maintenance.finance import (
    CLASSIFICATION_CONFIDENCES,
    LEDGER_CATEGORY_TREE,
    PAYMENT_STATUSES,
    TRANSACTION_TYPES,
)


DETAIL_HEADERS = (
    "记录编号", "项目名称", "发生日期", "收支类型", "一级分类", "二级分类",
    "事项摘要", "金额（元）", "经办/垫付人", "支付状态", "支付日期",
    "支付/报销说明", "备注（原始用途/购买原因）", "分类置信度",
    "来源文件", "来源工作表", "原始行号",
)
PENDING_HEADERS = (
    "记录类型", "项目名称", "发生日期", "事项/原始用途", "当前一级分类",
    "当前二级分类", "待确认问题", "经办/垫付人", "支付说明", "来源文件",
    "来源工作表", "原始行号",
)


@dataclass(frozen=True)
class LedgerEntry:
    source_record_id: str
    project_name: str
    entry_date: str
    transaction_type: str
    primary_category: str
    secondary_category: str
    summary: str
    amount: float
    handler_name: str
    payment_status: str
    payment_date: str
    payment_notes: str
    original_notes: str
    classification_confidence: str
    source_filename: str
    source_sheet: str
    source_row: int
    review_status: str


@dataclass(frozen=True)
class PendingLedgerItem:
    project_name: str
    item_date: str
    summary: str
    primary_category: str
    secondary_category: str
    handler_name: str
    payment_notes: str
    source_filename: str
    source_sheet: str
    source_row: int
    issue_type: str


@dataclass(frozen=True)
class LedgerImportPreview:
    project_names: tuple[str, ...]
    entries: tuple[LedgerEntry, ...]
    pending_items: tuple[PendingLedgerItem, ...]
    totals: dict[str, float]

    @property
    def project_count(self) -> int:
        return len(self.project_names)


def _iso_date(value, *, field: str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field}不是有效日期") from exc


def _headers(sheet, expected: tuple[str, ...]) -> dict[str, int]:
    values = [cell.value for cell in sheet[3]]
    positions = {str(value).strip(): index for index, value in enumerate(values) if value}
    missing = [name for name in expected if name not in positions]
    if missing:
        raise ValueError(f"缺少字段: {', '.join(missing)}")
    return positions


def _value(row, positions: dict[str, int], name: str):
    index = positions[name]
    return row[index] if index < len(row) else None


def _category_pairs() -> dict[tuple[str, str], str]:
    return {
        (primary, secondary): scope
        for primary, (scope, secondaries) in LEDGER_CATEGORY_TREE.items()
        for secondary in secondaries
    }


def _parse_workbook(workbook, workbook_name: str):
    if "费用明细" not in workbook.sheetnames or "待确认清单" not in workbook.sheetnames:
        raise ValueError(f"{workbook_name}: 必须包含费用明细和待确认清单")

    pending_sheet = workbook["待确认清单"]
    pending_headers = _headers(pending_sheet, PENDING_HEADERS)
    review_keys: set[tuple[str, str, int]] = set()
    pending_items: list[PendingLedgerItem] = []
    project_names: set[str] = set()
    category_pairs = _category_pairs()
    for excel_row, row in enumerate(
        pending_sheet.iter_rows(min_row=4, values_only=True), start=4
    ):
        record_type = str(_value(row, pending_headers, "记录类型") or "").strip()
        if not record_type:
            continue
        project_name = str(_value(row, pending_headers, "项目名称") or "").strip()
        source_filename = str(_value(row, pending_headers, "来源文件") or "").strip()
        source_sheet = str(_value(row, pending_headers, "来源工作表") or "").strip()
        try:
            source_row = int(_value(row, pending_headers, "原始行号"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{workbook_name}/待确认清单/{excel_row}: 原始行号无效") from exc
        project_names.add(project_name)
        key = (source_filename, source_sheet, source_row)
        if record_type == "有金额待复核":
            review_keys.add(key)
            continue
        if record_type != "缺少金额":
            raise ValueError(f"{workbook_name}/待确认清单/{excel_row}: 记录类型无效")
        primary = str(_value(row, pending_headers, "当前一级分类") or "").strip()
        secondary = str(_value(row, pending_headers, "当前二级分类") or "").strip()
        if (primary, secondary) not in category_pairs:
            raise ValueError(f"{workbook_name}/待确认清单/{excel_row}: 分类不存在")
        pending_items.append(PendingLedgerItem(
            project_name=project_name,
            item_date=_iso_date(_value(row, pending_headers, "发生日期"), field="发生日期"),
            summary=str(_value(row, pending_headers, "事项/原始用途") or "").strip(),
            primary_category=primary,
            secondary_category=secondary,
            handler_name=str(_value(row, pending_headers, "经办/垫付人") or "").strip(),
            payment_notes=str(_value(row, pending_headers, "支付说明") or "").strip(),
            source_filename=source_filename,
            source_sheet=source_sheet,
            source_row=source_row,
            issue_type=str(_value(row, pending_headers, "待确认问题") or "").strip(),
        ))

    detail_sheet = workbook["费用明细"]
    detail_headers = _headers(detail_sheet, DETAIL_HEADERS)
    entries: list[LedgerEntry] = []
    for excel_row, row in enumerate(
        detail_sheet.iter_rows(min_row=4, values_only=True), start=4
    ):
        record_id = str(_value(row, detail_headers, "记录编号") or "").strip()
        if not record_id:
            continue
        project_name = str(_value(row, detail_headers, "项目名称") or "").strip()
        project_names.add(project_name)
        transaction_type = str(_value(row, detail_headers, "收支类型") or "").strip()
        if transaction_type not in TRANSACTION_TYPES:
            raise ValueError(f"{workbook_name}/费用明细/{excel_row}: 收支类型无效")
        primary = str(_value(row, detail_headers, "一级分类") or "").strip()
        secondary = str(_value(row, detail_headers, "二级分类") or "").strip()
        scope = category_pairs.get((primary, secondary))
        expected_scope = "支出" if transaction_type in {"支出", "冲减支出"} else transaction_type
        if scope != expected_scope:
            raise ValueError(f"{workbook_name}/费用明细/{excel_row}: 分类与收支类型不匹配")
        amount = _value(row, detail_headers, "金额（元）")
        if not isinstance(amount, (int, float)) or not math.isfinite(float(amount)) or amount <= 0:
            raise ValueError(f"{workbook_name}/费用明细/{excel_row}: 金额无效")
        payment_status = str(_value(row, detail_headers, "支付状态") or "").strip()
        if payment_status not in PAYMENT_STATUSES:
            raise ValueError(f"{workbook_name}/费用明细/{excel_row}: 付款状态无效")
        confidence = str(_value(row, detail_headers, "分类置信度") or "").strip()
        if confidence and confidence not in CLASSIFICATION_CONFIDENCES:
            raise ValueError(f"{workbook_name}/费用明细/{excel_row}: 分类置信度无效")
        source_filename = str(_value(row, detail_headers, "来源文件") or "").strip()
        source_sheet = str(_value(row, detail_headers, "来源工作表") or "").strip()
        try:
            source_row = int(_value(row, detail_headers, "原始行号"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{workbook_name}/费用明细/{excel_row}: 原始行号无效") from exc
        payment_date_value = _value(row, detail_headers, "支付日期")
        entries.append(LedgerEntry(
            source_record_id=record_id,
            project_name=project_name,
            entry_date=_iso_date(_value(row, detail_headers, "发生日期"), field="发生日期"),
            transaction_type=transaction_type,
            primary_category=primary,
            secondary_category=secondary,
            summary=str(_value(row, detail_headers, "事项摘要") or "").strip(),
            amount=float(amount),
            handler_name=str(_value(row, detail_headers, "经办/垫付人") or "").strip(),
            payment_status=payment_status,
            payment_date=_iso_date(payment_date_value, field="支付日期") if payment_date_value else "",
            payment_notes=str(_value(row, detail_headers, "支付/报销说明") or "").strip(),
            original_notes=str(_value(row, detail_headers, "备注（原始用途/购买原因）") or "").strip(),
            classification_confidence=confidence,
            source_filename=source_filename,
            source_sheet=source_sheet,
            source_row=source_row,
            review_status=(
                "待复核" if (source_filename, source_sheet, source_row) in review_keys else "已确认"
            ),
        ))
    if len(project_names) != 1:
        raise ValueError(f"{workbook_name}: 一个账套只能包含一个项目")
    return entries, pending_items, project_names


def parse_ledger_source(path: Path) -> LedgerImportPreview:
    path = Path(path)
    workbook_sources: list[tuple[str, object]] = []
    if path.suffix.lower() == ".xlsx":
        workbook_sources.append((path.name, path))
    elif path.suffix.lower() == ".zip":
        try:
            with ZipFile(path) as archive:
                for member in archive.infolist():
                    member_path = PurePosixPath(member.filename)
                    if (
                        member_path.is_absolute()
                        or ".." in member_path.parts
                        or "\\" in member.filename
                    ):
                        raise ValueError(f"不安全的压缩包路径: {member.filename}")
                    if member.is_dir() or len(member_path.parts) != 1:
                        continue
                    if member_path.suffix.lower() == ".xlsx":
                        workbook_sources.append((member_path.name, BytesIO(archive.read(member))))
        except BadZipFile as exc:
            raise ValueError("压缩包损坏") from exc
    else:
        raise ValueError("仅支持 ZIP 或 XLSX 账套")
    if not workbook_sources:
        raise ValueError("没有找到可导入的 XLSX 账套")

    entries: list[LedgerEntry] = []
    pending_items: list[PendingLedgerItem] = []
    projects: set[str] = set()
    record_ids: set[str] = set()
    for workbook_name, source in workbook_sources:
        workbook = load_workbook(source, read_only=True, data_only=False)
        parsed_entries, parsed_pending, parsed_projects = _parse_workbook(workbook, workbook_name)
        for entry in parsed_entries:
            if entry.source_record_id in record_ids:
                raise ValueError(f"重复记录编号: {entry.source_record_id}")
            record_ids.add(entry.source_record_id)
        entries.extend(parsed_entries)
        pending_items.extend(parsed_pending)
        projects.update(parsed_projects)

    totals = {
        "expense": sum(e.amount for e in entries if e.transaction_type == "支出"),
        "expense_reduction": sum(e.amount for e in entries if e.transaction_type == "冲减支出"),
        "income": sum(e.amount for e in entries if e.transaction_type == "收入"),
        "fund_transfer": sum(e.amount for e in entries if e.transaction_type == "资金往来"),
    }
    totals["net_expense"] = totals["expense"] - totals["expense_reduction"]
    return LedgerImportPreview(
        project_names=tuple(sorted(projects)),
        entries=tuple(entries),
        pending_items=tuple(pending_items),
        totals=totals,
    )
