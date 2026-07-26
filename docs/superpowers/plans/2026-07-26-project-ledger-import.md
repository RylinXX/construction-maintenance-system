# 项目账套结构化导入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 6 个项目的 4,907 条正式财务明细和 276 条待补录事项安全导入 PAM，并把现有扁平费用科目升级为可审计的分层项目账套。

**Architecture:** 保留现有 Flask/Jinja2/SQLite 分层，在 `expense_categories` 和 `vouchers` 上做向后兼容的增量迁移，新建 `ledger_pending_items` 保存缺少金额的事项。新增独立的账套解析/导入服务和 Flask CLI，页面、看板和导出统一通过仓储层使用同一财务口径。

**Tech Stack:** Python 3.11、Flask 3、SQLite、Jinja2、openpyxl、Click/Flask CLI、pytest、Nginx、systemd。

---

## Scope And File Map

This is one integrated migration: the schema, importer, reporting, UI, and deployment checks all serve the same imported ledger and cannot ship independently without producing incomplete financial results.

- `construction_maintenance/finance.py`: canonical transaction/payment/review constants and the 12-root/59-leaf category tree.
- `construction_maintenance/db.py`: additive SQLite migrations, pending-item table, indexes, and category seeding.
- `construction_maintenance/repositories.py`: structured voucher CRUD, financial filters/summaries, category integrity, pending-item conversion.
- `construction_maintenance/services/ledger_import.py`: ZIP/XLSX parsing, validation, dry-run preview, seed cleanup, idempotent transactional import.
- `construction_maintenance/commands.py`: `flask ledger-import` command and human-readable preview output.
- `construction_maintenance/app.py`: command registration and version bump.
- `construction_maintenance/services/dashboard.py`: correct expense/reduction/income/fund-transfer KPIs.
- `construction_maintenance/services/exports.py`: complete project-ledger export with source/review columns.
- `construction_maintenance/web/routes.py`: filters, structured create/edit flows, pending-item completion, category migration.
- `construction_maintenance/templates/project_vouchers.html`: project account KPIs, filters, detailed fields, and review status.
- `construction_maintenance/templates/vouchers.html`: cross-project structured ledger list and entry form.
- `construction_maintenance/templates/expense_categories.html`: parent/child category management.
- `construction_maintenance/templates/ledger_pending.html`: missing-amount queue and conversion form.
- `construction_maintenance/templates/dashboard.html`: revised financial KPI labels.
- `construction_maintenance/static/app.css`: compact ledger filters, category tree, and pending queue responsive rules.
- `tests/test_finance_schema.py`: migration and category-tree coverage.
- `tests/test_financial_repositories.py`: structured entries, summaries, category guards, and pending conversion.
- `tests/test_ledger_import.py`: parser, validation, cleanup isolation, idempotency, and exact totals.
- `tests/test_financial_reporting.py`: dashboard and Excel financial semantics.
- `tests/test_ledger_routes.py`: form, filter, category, and pending-item route coverage.
- `scripts/verify_ledger_import_copy.py`: import into a copied production DB and prove protected-table preservation plus exact totals.
- `deploy/nginx-pam.conf.example`: TLS 1.2/1.3 and 20 MB request limit.
- `docs/runbooks/2026-07-26-project-ledger-production-import.md`: exact backup, deploy, import, verification, and rollback commands.

## Source Acceptance Constants

All final checks use these approved source totals:

```python
EXPECTED_IMPORT = {
    "projects": 6,
    "entries": 4907,
    "review_entries": 483,
    "pending_items": 276,
    "expense": 11_643_311.78,
    "expense_reduction": 17_573.00,
    "net_expense": 11_625_738.78,
    "income": 43_670.00,
    "fund_transfer": 50_128.83,
}
```

### Task 1: Freeze And Commit The Existing Functional-Audit Baseline

**Files:**
- Modify/verify: `README.md`
- Modify/verify: `construction_maintenance/app.py`
- Modify/verify: `construction_maintenance/config.py`
- Modify/verify: `construction_maintenance/db.py`
- Modify/verify: `construction_maintenance/repositories.py`
- Modify/verify: `construction_maintenance/security.py`
- Modify/verify: `construction_maintenance/services/exports.py`
- Modify/verify: `construction_maintenance/services/imports.py`
- Modify/verify: `construction_maintenance/services/ocr.py`
- Modify/verify: `construction_maintenance/templates/attendance.html`
- Modify/verify: `construction_maintenance/templates/batch.html`
- Modify/verify: `construction_maintenance/templates/people.html`
- Modify/verify: `construction_maintenance/templates/project_vouchers.html`
- Modify/verify: `construction_maintenance/templates/settings.html`
- Modify/verify: `construction_maintenance/templates/vouchers.html`
- Modify/verify: `construction_maintenance/web/routes.py`
- Modify/verify: `pyproject.toml`
- Test: `tests/test_attendance.py`
- Test: `tests/test_functional_audit_fixes.py`
- Test: `tests/test_ocr.py`
- Test: `tests/test_routes.py`
- Test: `tests/test_security.py`
- Documentation: `docs/functional-test-fix-checklist-2026-07-20.md`
- Deployment: `deploy/nginx-pam.conf.example`

- [ ] **Step 1: Confirm the current dirty changes match the functional-audit checklist**

Run:

```bash
git diff --check
git diff --stat
git status --short
```

Expected: no whitespace errors; only the files listed above plus the already committed design/plan documents are present.

- [ ] **Step 2: Run the existing regression baseline**

Run:

```bash
.venv/bin/pytest -q
```

Expected: `104 passed`; SWIG deprecation warnings are allowed, failures are not.

- [ ] **Step 3: Commit only the verified functional-audit baseline**

Run:

```bash
git add README.md pyproject.toml deploy/nginx-pam.conf.example docs/functional-test-fix-checklist-2026-07-20.md
git add construction_maintenance/app.py construction_maintenance/config.py construction_maintenance/db.py construction_maintenance/repositories.py construction_maintenance/security.py
git add construction_maintenance/services/exports.py construction_maintenance/services/imports.py construction_maintenance/services/ocr.py
git add construction_maintenance/templates/attendance.html construction_maintenance/templates/batch.html construction_maintenance/templates/people.html construction_maintenance/templates/project_vouchers.html construction_maintenance/templates/settings.html construction_maintenance/templates/vouchers.html
git add construction_maintenance/web/routes.py tests/test_attendance.py tests/test_functional_audit_fixes.py tests/test_ocr.py tests/test_routes.py tests/test_security.py
git commit -m "fix: harden production workflows"
```

Expected: one commit containing the tested audit fixes; no source file from the new ledger work is included.

### Task 2: Add Finance Constants, Hierarchical Categories, And Schema Migration

**Files:**
- Create: `construction_maintenance/finance.py`
- Modify: `construction_maintenance/db.py:11-19,80-102,215-240,320-347`
- Create: `tests/test_finance_schema.py`
- Modify: `tests/test_db.py:18-93`

- [ ] **Step 1: Write failing schema and category-tree tests**

Create `tests/test_finance_schema.py`:

```python
from construction_maintenance.db import get_db, init_db
from construction_maintenance.finance import LEDGER_CATEGORY_TREE


def test_finance_schema_has_structured_entry_and_pending_columns(app):
    with app.app_context():
        init_db()
        db = get_db()
        voucher_columns = {
            row["name"] for row in db.execute("pragma table_info(vouchers)")
        }
        pending_columns = {
            row["name"] for row in db.execute("pragma table_info(ledger_pending_items)")
        }

    assert {
        "source_record_id", "transaction_type", "category_id", "handler_name",
        "payment_status", "payment_date", "payment_notes", "review_status",
        "classification_confidence", "source_filename", "source_sheet",
        "source_row", "original_notes",
    }.issubset(voucher_columns)
    assert {
        "project_id", "item_date", "summary", "suggested_category_id",
        "handler_name", "payment_notes", "source_filename", "source_sheet",
        "source_row", "issue_type", "status", "voucher_id",
    }.issubset(pending_columns)


def test_ledger_category_tree_is_seeded_idempotently(app):
    with app.app_context():
        init_db()
        init_db()
        db = get_db()
        roots = db.execute(
            "select * from expense_categories where parent_id is null and is_active = 1"
        ).fetchall()
        leaves = db.execute(
            "select * from expense_categories where parent_id is not null and is_active = 1"
        ).fetchall()

    assert len(LEDGER_CATEGORY_TREE) == 12
    assert len(roots) == 12
    assert len(leaves) == 59
    assert {row["transaction_scope"] for row in roots} == {
        "支出", "收入", "资金往来"
    }
```

- [ ] **Step 2: Run the tests and verify the old schema fails**

Run:

```bash
.venv/bin/pytest tests/test_finance_schema.py -q
```

Expected: FAIL because `construction_maintenance.finance` and `ledger_pending_items` do not exist.

- [ ] **Step 3: Add canonical finance values and the complete category tree**

Create `construction_maintenance/finance.py`:

```python
from __future__ import annotations

TRANSACTION_TYPES = ("支出", "冲减支出", "收入", "资金往来")
PAYMENT_STATUSES = (
    "已支付/已报销",
    "已垫付，报销待确认",
    "未支付",
    "支付状态待确认",
)
REVIEW_STATUSES = ("已确认", "待复核")
CLASSIFICATION_CONFIDENCES = ("高", "中", "低")
PENDING_STATUSES = ("待补录", "已转正式明细", "已忽略")
LEGACY_CATEGORY_MAP = {
    "员工报销": "其他及待确认",
    "转账凭证": "其他及待确认",
    "材料费用": "五金辅材及工具",
    "油费": "车辆燃油",
    "电费": "电费",
    "人工工资": "工资及人员报酬",
    "其它": "其他及待确认",
}

LEDGER_CATEGORY_TREE = {
    "人工成本": ("支出", ("劳务及临时用工", "司机及操作手费用", "工资及人员报酬")),
    "商务及前期费": ("支出", ("商务招待及礼品", "开票及税费", "技术服务及手续", "投标及代理费", "行政及其他服务费")),
    "安全文明施工费": ("支出", ("人员体检及检测", "保洁及环保", "劳保及安全防护")),
    "机械设备费": ("支出", ("其他机械设备费", "挖掘机及破碎设备台班", "机械设备租赁", "水车及环保设备台班", "维修保养及配件", "设备购置", "设备进退场及拖运", "起重及装卸设备", "运输车辆台班", "铲车及装载机台班")),
    "材料费": ("支出", ("五金辅材及工具", "木材及模板", "水泥", "混凝土", "干拌料及砂浆", "电气材料", "砂石骨料及回填料", "钢材及焊材")),
    "燃料动力费": ("支出", ("取暖燃料", "机械燃油", "水费", "电费", "车辆燃油")),
    "财务及其他": ("支出", ("其他及待确认", "罚款及赔偿")),
    "车辆费用": ("支出", ("保险及年检", "维修保养", "违章罚款")),
    "运输及处置费": ("支出", ("其他运输费", "土方外运及消纳", "差旅交通", "材料运输费", "货运及配送", "通行及停车费")),
    "项目现场管理费": ("支出", ("伙食费", "办公用品及资料", "开工及现场活动", "快递及资料寄送", "房租及场地费", "生活及宿舍用品", "通讯网络及软件")),
    "收入": ("收入", ("废料处置收入", "押金退回", "退款及退回")),
    "资金往来": ("资金往来", ("借款及预支", "备用金", "押金及保证金", "预付款及定金")),
}
```

- [ ] **Step 4: Add additive migrations and idempotent category seeding**

In `construction_maintenance/db.py`, add this helper before `init_db()`:

```python
def _ensure_column(db: sqlite3.Connection, table: str, name: str, ddl: str) -> None:
    columns = {row["name"] for row in db.execute(f"pragma table_info({table})")}
    if name not in columns:
        db.execute(f"alter table {table} add column {name} {ddl}")


def _seed_ledger_categories(db: sqlite3.Connection) -> None:
    from .finance import LEDGER_CATEGORY_TREE

    for root_order, (root_name, (scope, leaves)) in enumerate(
        LEDGER_CATEGORY_TREE.items(), start=1
    ):
        db.execute(
            """
            insert into expense_categories
              (name, parent_id, transaction_scope, sort_order, is_active)
            values (?, null, ?, ?, 1)
            on conflict(name) do update set
              parent_id = null,
              transaction_scope = excluded.transaction_scope,
              sort_order = excluded.sort_order,
              is_active = 1
            """,
            (root_name, scope, root_order * 100),
        )
        root_id = db.execute(
            "select id from expense_categories where name = ?", (root_name,)
        ).fetchone()["id"]
        for leaf_order, leaf_name in enumerate(leaves, start=1):
            db.execute(
                """
                insert into expense_categories
                  (name, parent_id, transaction_scope, sort_order, is_active)
                values (?, ?, ?, ?, 1)
                on conflict(name) do update set
                  parent_id = excluded.parent_id,
                  transaction_scope = excluded.transaction_scope,
                  sort_order = excluded.sort_order,
                  is_active = 1
                """,
                (leaf_name, root_id, scope, leaf_order * 10),
            )

    legacy_names = (
        "员工报销", "转账凭证", "材料费用", "油费", "人工工资", "其它"
    )
    db.executemany(
        "update expense_categories set is_active = 0 where name = ?",
        ((name,) for name in legacy_names),
    )
```

Add `parent_id` and `transaction_scope` to the `expense_categories` create statement. Add the approved structured columns to the `vouchers` create statement. Add this table and indexes to the main schema script:

```sql
create table if not exists ledger_pending_items (
    id integer primary key autoincrement,
    project_id integer not null references projects(id),
    item_date text not null,
    summary text not null,
    suggested_category_id integer references expense_categories(id),
    handler_name text not null default '',
    payment_notes text not null default '',
    source_filename text not null,
    source_sheet text not null,
    source_row integer not null,
    issue_type text not null,
    status text not null default '待补录',
    voucher_id integer references vouchers(id),
    created_at text not null default current_timestamp,
    unique(project_id, source_filename, source_sheet, source_row)
);

create unique index if not exists idx_vouchers_source_record_id
    on vouchers(source_record_id) where source_record_id is not null;
create index if not exists idx_vouchers_financial_filters
    on vouchers(project_id, transaction_type, category_id, payment_status, review_status);
create index if not exists idx_pending_project_status
    on ledger_pending_items(project_id, status, item_date);
```

Use `_ensure_column()` for every approved `vouchers` field and for `expense_categories.parent_id` / `transaction_scope`, then call `_seed_ledger_categories(db)` before the final commit in `init_db()`.

The exact migration calls are:

```python
_ensure_column(db, "expense_categories", "parent_id", "integer references expense_categories(id)")
_ensure_column(db, "expense_categories", "transaction_scope", "text not null default '支出'")
_ensure_column(db, "vouchers", "source_record_id", "text")
_ensure_column(db, "vouchers", "transaction_type", "text not null default '支出'")
_ensure_column(db, "vouchers", "category_id", "integer references expense_categories(id)")
_ensure_column(db, "vouchers", "handler_name", "text not null default ''")
_ensure_column(db, "vouchers", "payment_status", "text not null default '支付状态待确认'")
_ensure_column(db, "vouchers", "payment_date", "text not null default ''")
_ensure_column(db, "vouchers", "payment_notes", "text not null default ''")
_ensure_column(db, "vouchers", "review_status", "text not null default '已确认'")
_ensure_column(db, "vouchers", "classification_confidence", "text not null default ''")
_ensure_column(db, "vouchers", "source_filename", "text not null default ''")
_ensure_column(db, "vouchers", "source_sheet", "text not null default ''")
_ensure_column(db, "vouchers", "source_row", "integer")
_ensure_column(db, "vouchers", "original_notes", "text not null default ''")
_seed_ledger_categories(db)
```

- [ ] **Step 5: Run migration tests and the existing DB tests**

Run:

```bash
.venv/bin/pytest tests/test_finance_schema.py tests/test_db.py -q
```

Expected: PASS, including two consecutive `init_db()` calls with exactly 12 active roots and 59 active leaves.

- [ ] **Step 6: Commit the schema unit**

Run:

```bash
git add construction_maintenance/finance.py construction_maintenance/db.py tests/test_finance_schema.py tests/test_db.py
git commit -m "feat: add structured project finance schema"
```

### Task 3: Implement Structured Financial Repositories And Pending Conversion

**Files:**
- Modify: `construction_maintenance/repositories.py:400-664,999-1023`
- Create: `tests/test_financial_repositories.py`
- Modify: `tests/test_repositories.py:8-115`

- [ ] **Step 1: Write failing repository tests for categories, totals, and pending conversion**

Create `tests/test_financial_repositories.py`:

```python
import pytest

from construction_maintenance import repositories as repo
from construction_maintenance.db import get_db


def _leaf_id(name: str) -> int:
    return int(get_db().execute(
        "select id from expense_categories where name = ? and parent_id is not null",
        (name,),
    ).fetchone()["id"])


def test_structured_entries_produce_correct_project_summary(app):
    with app.app_context():
        company = repo.get_main_company()
        project_id = repo.create_project({"company_id": company["id"], "name": "测试项目"})
        rows = [
            ("支出", "材料运输费", 1000),
            ("冲减支出", "材料运输费", 100),
            ("收入", "废料处置收入", 50),
            ("资金往来", "备用金", 200),
        ]
        for index, (transaction_type, category, amount) in enumerate(rows, start=1):
            repo.create_voucher({
                "project_id": project_id,
                "voucher_date": "2026-07-01",
                "transaction_type": transaction_type,
                "category_id": _leaf_id(category),
                "amount": amount,
                "source_record_id": f"TEST-{index}",
                "payment_status": "未支付",
            })
        summary = repo.get_project_financial_summary(project_id)

    assert summary == {
        "expense": 1000.0,
        "expense_reduction": 100.0,
        "net_expense": 900.0,
        "income": 50.0,
        "fund_transfer": 200.0,
        "unsettled": 900.0,
        "entry_count": 4,
        "review_count": 0,
        "pending_count": 0,
    }


def test_used_leaf_category_cannot_be_deleted(app):
    with app.app_context():
        company = repo.get_main_company()
        project_id = repo.create_project({"company_id": company["id"], "name": "分类保护"})
        category_id = _leaf_id("机械燃油")
        repo.create_voucher({
            "project_id": project_id,
            "voucher_date": "2026-07-01",
            "transaction_type": "支出",
            "category_id": category_id,
            "amount": 300,
        })
        with pytest.raises(ValueError, match="已被财务明细使用"):
            repo.delete_expense_category(category_id)


def test_pending_item_converts_once_to_structured_entry(app):
    with app.app_context():
        company = repo.get_main_company()
        project_id = repo.create_project({"company_id": company["id"], "name": "待补录项目"})
        category_id = _leaf_id("运输车辆台班")
        item_id = repo.create_ledger_pending_item({
            "project_id": project_id,
            "item_date": "2026-03-17",
            "summary": "大车两个台班",
            "suggested_category_id": category_id,
            "source_filename": "source.xls",
            "source_sheet": "汇总",
            "source_row": 7,
            "issue_type": "缺少金额",
        })
        voucher_id = repo.convert_ledger_pending_item(
            item_id,
            amount=1200,
            category_id=category_id,
            transaction_type="支出",
            payment_status="支付状态待确认",
            actor_admin_id=None,
        )
        item = repo.get_ledger_pending_item(item_id)
        with pytest.raises(ValueError, match="已经转换"):
            repo.convert_ledger_pending_item(
                item_id,
                amount=1200,
                category_id=category_id,
                transaction_type="支出",
                payment_status="支付状态待确认",
                actor_admin_id=None,
            )

    assert item["status"] == "已转正式明细"
    assert item["voucher_id"] == voucher_id
```

- [ ] **Step 2: Run the focused tests and verify the repository API is missing**

Run:

```bash
.venv/bin/pytest tests/test_financial_repositories.py -q
```

Expected: FAIL on missing `get_project_financial_summary` and pending-item functions.

- [ ] **Step 3: Add strict financial validators and structured voucher insertion**

In `construction_maintenance/repositories.py`, import the finance constants and add:

```python
def _validated_choice(value: Any, label: str, choices: tuple[str, ...]) -> str:
    text = str(value or "").strip()
    if text not in choices:
        raise ValueError(f"{label}无效")
    return text


def _get_leaf_category(category_id: int):
    row = get_db().execute(
        """
        select leaf.*, parent.name as primary_name
        from expense_categories leaf
        join expense_categories parent on parent.id = leaf.parent_id
        where leaf.id = ? and leaf.is_active = 1 and parent.is_active = 1
        """,
        (category_id,),
    ).fetchone()
    if row is None:
        raise ValueError("二级分类不存在或已停用")
    return row


def _insert_voucher(db: sqlite3.Connection, data: dict[str, Any]) -> int:
    from .finance import (
        CLASSIFICATION_CONFIDENCES,
        PAYMENT_STATUSES,
        REVIEW_STATUSES,
        TRANSACTION_TYPES,
    )

    amount = normalize_amount(data["amount"])
    voucher_date = _validated_date(data.get("voucher_date"), "凭证日期", required=True)
    transaction_type = _validated_choice(
        data.get("transaction_type", "支出"), "收支类型", TRANSACTION_TYPES
    )
    category = _get_leaf_category(int(data["category_id"]))
    expected_scope = "支出" if transaction_type in {"支出", "冲减支出"} else transaction_type
    if category["transaction_scope"] != expected_scope:
        raise ValueError("分类与收支类型不匹配")
    payment_status = _validated_choice(
        data.get("payment_status", "支付状态待确认"), "付款状态", PAYMENT_STATUSES
    )
    review_status = _validated_choice(
        data.get("review_status", "已确认"), "复核状态", REVIEW_STATUSES
    )
    confidence = str(data.get("classification_confidence") or "").strip()
    if confidence and confidence not in CLASSIFICATION_CONFIDENCES:
        raise ValueError("分类置信度无效")
    cursor = db.execute(
        """
        insert into vouchers (
          project_id, voucher_date, voucher_type, amount, notes, attachment_path,
          entry_user, source_record_id, transaction_type, category_id, handler_name,
          payment_status, payment_date, payment_notes, review_status,
          classification_confidence, source_filename, source_sheet, source_row,
          original_notes
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(data["project_id"]), voucher_date, category["name"], amount,
            str(data.get("notes") or ""), str(data.get("attachment_path") or ""),
            str(data.get("entry_user") or ""), data.get("source_record_id"),
            transaction_type, category["id"], str(data.get("handler_name") or ""),
            payment_status, _validated_date(data.get("payment_date"), "付款日期"),
            str(data.get("payment_notes") or ""), review_status, confidence,
            str(data.get("source_filename") or ""), str(data.get("source_sheet") or ""),
            data.get("source_row"), str(data.get("original_notes") or ""),
        ),
    )
    return int(cursor.lastrowid)
```

Refactor `create_voucher()` to call `_insert_voucher()`, write the existing audit event, and commit once. Preserve the seven legacy callers by resolving `voucher_type` through `LEGACY_CATEGORY_MAP` when `category_id` is absent:

```python
if not data.get("category_id"):
    from .finance import LEGACY_CATEGORY_MAP

    legacy_name = _required_text(data.get("voucher_type"), "凭证类型")
    leaf_name = LEGACY_CATEGORY_MAP.get(legacy_name, legacy_name)
    leaf = get_db().execute(
        """
        select id from expense_categories
        where name = ? and parent_id is not null and is_active = 1
        """,
        (leaf_name,),
    ).fetchone()
    if leaf is None:
        raise ValueError("凭证类型没有对应的启用二级分类")
    data = {**data, "category_id": int(leaf["id"])}
```

- [ ] **Step 4: Add filtered reads and one authoritative summary query**

Implement `list_vouchers()` with keyword filters for transaction type, primary category, leaf category, payment status, review status, and date range. Join the leaf and parent category names. Add:

```python
def list_vouchers(
    project_id: int | None = None,
    *,
    include_voided: bool = False,
    transaction_type: str | None = None,
    primary_category_id: int | None = None,
    category_id: int | None = None,
    payment_status: str | None = None,
    review_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    conditions: list[str] = []
    params: list[Any] = []
    filters = (
        (project_id, "vouchers.project_id = ?"),
        (transaction_type, "vouchers.transaction_type = ?"),
        (primary_category_id, "parent.id = ?"),
        (category_id, "leaf.id = ?"),
        (payment_status, "vouchers.payment_status = ?"),
        (review_status, "vouchers.review_status = ?"),
    )
    for value, condition in filters:
        if value not in (None, ""):
            conditions.append(condition)
            params.append(value)
    if date_from:
        conditions.append("vouchers.voucher_date >= ?")
        params.append(_validated_date(date_from, "开始日期", required=True))
    if date_to:
        conditions.append("vouchers.voucher_date <= ?")
        params.append(_validated_date(date_to, "结束日期", required=True))
    if not include_voided:
        conditions.append("vouchers.is_void = 0")
    where = "where " + " and ".join(conditions) if conditions else ""
    return get_db().execute(
        f"""
        select vouchers.*, projects.name as project_name,
               leaf.name as secondary_category,
               parent.name as primary_category,
               parent.id as primary_category_id
        from vouchers
        join projects on projects.id = vouchers.project_id
        left join expense_categories leaf on leaf.id = vouchers.category_id
        left join expense_categories parent on parent.id = leaf.parent_id
        {where}
        order by vouchers.voucher_date desc, vouchers.id desc
        """,
        params,
    ).fetchall()


def get_project_financial_summary(project_id: int) -> dict[str, float | int]:
    row = get_db().execute(
        """
        select
          coalesce(sum(case when transaction_type = '支出' then amount else 0 end), 0) as expense,
          coalesce(sum(case when transaction_type = '冲减支出' then amount else 0 end), 0) as expense_reduction,
          coalesce(sum(case when transaction_type = '收入' then amount else 0 end), 0) as income,
          coalesce(sum(case when transaction_type = '资金往来' then amount else 0 end), 0) as fund_transfer,
          coalesce(sum(case
            when payment_status != '已支付/已报销' and transaction_type = '支出' then amount
            when payment_status != '已支付/已报销' and transaction_type = '冲减支出' then -amount
            else 0 end), 0) as unsettled,
          count(*) as entry_count,
          sum(case when review_status = '待复核' then 1 else 0 end) as review_count
        from vouchers
        where project_id = ? and is_void = 0
        """,
        (project_id,),
    ).fetchone()
    pending_count = get_db().execute(
        "select count(*) from ledger_pending_items where project_id = ? and status = '待补录'",
        (project_id,),
    ).fetchone()[0]
    expense = float(row["expense"])
    reduction = float(row["expense_reduction"])
    return {
        "expense": expense,
        "expense_reduction": reduction,
        "net_expense": expense - reduction,
        "income": float(row["income"]),
        "fund_transfer": float(row["fund_transfer"]),
        "unsettled": float(row["unsettled"]),
        "entry_count": int(row["entry_count"]),
        "review_count": int(row["review_count"] or 0),
        "pending_count": int(pending_count),
    }
```

- [ ] **Step 5: Add category guards and atomic pending conversion**

Add `create_ledger_pending_item`, `get_ledger_pending_item`, `list_ledger_pending_items`, and `convert_ledger_pending_item`. `convert_ledger_pending_item` must call `_insert_voucher()` on the existing connection, update the pending row, write an audit event, and commit only after all three operations succeed. Add `delete_expense_category()` that rejects categories referenced by vouchers or children and `migrate_expense_category()` that changes `category_id` and legacy `voucher_type` together.

Use these concrete repository functions:

```python
def create_ledger_pending_item(data: dict[str, Any]) -> int:
    db = get_db()
    cursor = db.execute(
        """
        insert into ledger_pending_items (
          project_id, item_date, summary, suggested_category_id, handler_name,
          payment_notes, source_filename, source_sheet, source_row, issue_type
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(data["project_id"]),
            _validated_date(data.get("item_date"), "发生日期", required=True),
            _required_text(data.get("summary"), "事项摘要", max_length=500),
            int(data["suggested_category_id"]),
            str(data.get("handler_name") or ""),
            str(data.get("payment_notes") or ""),
            _required_text(data.get("source_filename"), "来源文件"),
            _required_text(data.get("source_sheet"), "来源工作表"),
            int(data["source_row"]),
            _required_text(data.get("issue_type"), "待确认问题"),
        ),
    )
    db.commit()
    return int(cursor.lastrowid)


def get_ledger_pending_item(item_id: int):
    return get_db().execute(
        "select * from ledger_pending_items where id = ?", (item_id,)
    ).fetchone()


def list_ledger_pending_items(
    project_id: int | None = None, status: str | None = None
):
    conditions: list[str] = []
    params: list[Any] = []
    if project_id is not None:
        conditions.append("items.project_id = ?")
        params.append(project_id)
    if status:
        conditions.append("items.status = ?")
        params.append(status)
    where = "where " + " and ".join(conditions) if conditions else ""
    return get_db().execute(
        f"""
        select items.*, projects.name as project_name,
               categories.name as suggested_category_name,
               parents.name as suggested_primary_name
        from ledger_pending_items items
        join projects on projects.id = items.project_id
        left join expense_categories categories on categories.id = items.suggested_category_id
        left join expense_categories parents on parents.id = categories.parent_id
        {where}
        order by items.item_date, items.id
        """,
        params,
    ).fetchall()


def convert_ledger_pending_item(
    item_id: int,
    *,
    amount: Any,
    category_id: int,
    transaction_type: str,
    payment_status: str,
    actor_admin_id: int | None,
) -> int:
    db = get_db()
    item = db.execute(
        "select * from ledger_pending_items where id = ?", (item_id,)
    ).fetchone()
    if item is None:
        raise ValueError("待补录事项不存在")
    if item["status"] != "待补录":
        raise ValueError("该待补录事项已经转换或忽略")
    source_record_id = (
        f"PENDING:{item['project_id']}:{item['source_filename']}:"
        f"{item['source_sheet']}:{item['source_row']}"
    )
    try:
        voucher_id = _insert_voucher(db, {
            "project_id": item["project_id"],
            "voucher_date": item["item_date"],
            "transaction_type": transaction_type,
            "category_id": category_id,
            "amount": amount,
            "notes": item["summary"],
            "handler_name": item["handler_name"],
            "payment_status": payment_status,
            "payment_notes": item["payment_notes"],
            "source_record_id": source_record_id,
            "source_filename": item["source_filename"],
            "source_sheet": item["source_sheet"],
            "source_row": item["source_row"],
            "original_notes": item["summary"],
        })
        db.execute(
            """
            update ledger_pending_items
            set status = '已转正式明细', voucher_id = ?
            where id = ? and status = '待补录'
            """,
            (voucher_id, item_id),
        )
        _insert_audit(
            db,
            actor_admin_id=actor_admin_id,
            action="convert",
            entity_type="ledger_pending_item",
            entity_id=item_id,
            details={"voucher_id": voucher_id},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return voucher_id


def ignore_ledger_pending_item(
    item_id: int, *, actor_admin_id: int | None
) -> None:
    db = get_db()
    item = db.execute(
        "select status from ledger_pending_items where id = ?", (item_id,)
    ).fetchone()
    if item is None:
        raise ValueError("待补录事项不存在")
    if item["status"] != "待补录":
        raise ValueError("只有待补录事项可以忽略")
    db.execute(
        "update ledger_pending_items set status = '已忽略' where id = ?",
        (item_id,),
    )
    _insert_audit(
        db,
        actor_admin_id=actor_admin_id,
        action="ignore",
        entity_type="ledger_pending_item",
        entity_id=item_id,
    )
    db.commit()


def delete_expense_category(category_id: int) -> None:
    db = get_db()
    category = db.execute(
        "select * from expense_categories where id = ?", (category_id,)
    ).fetchone()
    if category is None:
        raise ValueError("分类不存在")
    children = db.execute(
        "select count(*) from expense_categories where parent_id = ?", (category_id,)
    ).fetchone()[0]
    references = db.execute(
        "select count(*) from vouchers where category_id = ?", (category_id,)
    ).fetchone()[0]
    if children:
        raise ValueError("一级分类仍有二级分类，不能删除")
    if references:
        raise ValueError("分类已被财务明细使用，不能删除")
    db.execute("delete from expense_categories where id = ?", (category_id,))
    db.commit()


def migrate_expense_category(
    source_id: int, target_id: int, *, actor_admin_id: int | None
) -> None:
    db = get_db()
    source = _get_leaf_category(source_id)
    target = _get_leaf_category(target_id)
    if source_id == target_id:
        raise ValueError("迁移目标不能与原分类相同")
    if source["transaction_scope"] != target["transaction_scope"]:
        raise ValueError("只能迁移到同一收支范围的分类")
    db.execute(
        "update vouchers set category_id = ?, voucher_type = ? where category_id = ?",
        (target_id, target["name"], source_id),
    )
    db.execute(
        "update expense_categories set is_active = 0 where id = ?", (source_id,)
    )
    _insert_audit(
        db,
        actor_admin_id=actor_admin_id,
        action="migrate",
        entity_type="expense_category",
        entity_id=source_id,
        details={"target_id": target_id},
    )
    db.commit()
```

Replace `tests/test_repositories.py::test_expense_category_rename_updates_existing_vouchers` with a structured leaf test:

```python
from construction_maintenance.db import get_db


def test_expense_category_rename_updates_legacy_display_name(app):
    with app.app_context():
        category = get_db().execute(
            "select * from expense_categories where name = '其他机械设备费'"
        ).fetchone()
        main_company = repo.get_main_company()
        project_id = repo.create_project({
            "company_id": main_company["id"], "name": "道路维修"
        })
        repo.create_voucher({
            "project_id": project_id,
            "voucher_date": "2026-05-29",
            "transaction_type": "支出",
            "category_id": category["id"],
            "amount": 1200,
        })
        repo.update_expense_category(category["id"], {
            "name": "设备租赁",
            "parent_id": category["parent_id"],
            "transaction_scope": "支出",
            "sort_order": 30,
            "is_active": 1,
        })
        voucher = repo.list_vouchers(project_id=project_id)[0]

    assert voucher["voucher_type"] == "设备租赁"
    assert voucher["secondary_category"] == "设备租赁"
```

- [ ] **Step 6: Run repository tests**

Run:

```bash
.venv/bin/pytest tests/test_financial_repositories.py tests/test_repositories.py -q
```

Expected: PASS; legacy voucher creation tests remain supported through the compatibility resolver.

- [ ] **Step 7: Commit the repository unit**

Run:

```bash
git add construction_maintenance/repositories.py tests/test_financial_repositories.py tests/test_repositories.py
git commit -m "feat: add structured ledger repositories"
```

### Task 4: Build The Standard Ledger Parser

**Files:**
- Create: `construction_maintenance/services/ledger_import.py`
- Create: `tests/test_ledger_import.py`

- [ ] **Step 1: Write a representative workbook fixture and parser tests**

In `tests/test_ledger_import.py`, build an in-memory workbook with exact source headers:

```python
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from openpyxl import Workbook, load_workbook

from construction_maintenance.services.ledger_import import parse_ledger_source

DETAIL_HEADERS = [
    "记录编号", "项目名称", "发生日期", "年月", "收支类型", "一级分类",
    "二级分类", "事项摘要", "金额（元）", "净支出（元）", "收入金额（元）",
    "经办/垫付人", "支付状态", "支付日期", "支付/报销说明",
    "备注（原始用途/购买原因）", "审核标记", "分类置信度", "来源文件",
    "来源工作表", "原始行号", "原始金额（元）",
]
PENDING_HEADERS = [
    "记录类型", "项目名称", "发生日期", "事项/原始用途", "金额（元）",
    "当前一级分类", "当前二级分类", "待确认问题", "经办/垫付人",
    "支付说明", "来源文件", "来源工作表", "原始行号",
]


def make_ledger_zip(tmp_path: Path) -> Path:
    workbook = Workbook()
    detail = workbook.active
    detail.title = "费用明细"
    detail.append(["测试项目｜费用明细"])
    detail.append([])
    detail.append(DETAIL_HEADERS)
    detail.append([
        "测试-20260701-0001", "测试项目", "2026-07-01", "2026-07", "支出",
        "材料费", "五金辅材及工具", "工具采购", 100, 100, 0, "张三",
        "已支付/已报销", "2026-07-02", "现金支付", "原始备注", "", "高",
        "测试源.xls", "汇总", 8, 100,
    ])
    pending = workbook.create_sheet("待确认清单")
    pending.append(["测试项目｜待确认清单"])
    pending.append([])
    pending.append(PENDING_HEADERS)
    pending.append([
        "有金额待复核", "测试项目", "2026-07-01", "工具采购", 100,
        "材料费", "五金辅材及工具", "分类待确认", "张三", "现金支付",
        "测试源.xls", "汇总", 8,
    ])
    pending.append([
        "缺少金额", "测试项目", "2026-07-03", "吊车一个班", None,
        "机械设备费", "起重及装卸设备", "缺少金额/仅有业务数量记录",
        "李四", "", "测试源.xls", "汇总", 9,
    ])
    xlsx_path = tmp_path / "测试项目_标准费用账套.xlsx"
    workbook.save(xlsx_path)
    zip_path = tmp_path / "账套.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        archive.write(xlsx_path, xlsx_path.name)
    return zip_path


def test_parser_marks_review_and_separates_missing_amount(tmp_path):
    preview = parse_ledger_source(make_ledger_zip(tmp_path))

    assert preview.project_count == 1
    assert len(preview.entries) == 1
    assert preview.entries[0].review_status == "待复核"
    assert len(preview.pending_items) == 1
    assert preview.pending_items[0].summary == "吊车一个班"
    assert preview.totals["expense"] == 100


def mutate_workbook_in_zip(zip_path: Path, tmp_path: Path, mutation) -> Path:
    with ZipFile(zip_path) as archive:
        member_name = archive.namelist()[0]
        workbook_path = tmp_path / "mutated.xlsx"
        workbook_path.write_bytes(archive.read(member_name))
    workbook = load_workbook(workbook_path)
    mutation(workbook)
    workbook.save(workbook_path)
    mutated_zip = tmp_path / "mutated.zip"
    with ZipFile(mutated_zip, "w", ZIP_DEFLATED) as archive:
        archive.write(workbook_path, member_name)
    return mutated_zip


def test_parser_rejects_unknown_category(tmp_path):
    source = make_ledger_zip(tmp_path)
    invalid = mutate_workbook_in_zip(
        source, tmp_path, lambda workbook: setattr(
            workbook["费用明细"]["G4"], "value", "不存在分类"
        )
    )
    with pytest.raises(ValueError, match="分类与收支类型不匹配"):
        parse_ledger_source(invalid)


def test_parser_rejects_missing_sheet(tmp_path):
    source = make_ledger_zip(tmp_path)
    invalid = mutate_workbook_in_zip(
        source, tmp_path, lambda workbook: workbook.remove(workbook["费用明细"])
    )
    with pytest.raises(ValueError, match="必须包含费用明细和待确认清单"):
        parse_ledger_source(invalid)


def test_parser_rejects_zip_path_traversal(tmp_path):
    source = tmp_path / "unsafe.zip"
    with ZipFile(source, "w", ZIP_DEFLATED) as archive:
        archive.writestr("../账套.xlsx", b"invalid")
    with pytest.raises(ValueError, match="不安全的压缩包路径"):
        parse_ledger_source(source)
```

```python
def append_detail_copy(workbook, *, project_name=None):
    sheet = workbook["费用明细"]
    values = [cell.value for cell in sheet[4]]
    if project_name is not None:
        values[1] = project_name
        values[0] = "OTHER-20260701-0002"
    sheet.append(values)


def test_parser_rejects_mixed_projects(tmp_path):
    invalid = mutate_workbook_in_zip(
        make_ledger_zip(tmp_path), tmp_path,
        lambda workbook: append_detail_copy(workbook, project_name="另一个项目"),
    )
    with pytest.raises(ValueError, match="一个账套只能包含一个项目"):
        parse_ledger_source(invalid)


def test_parser_rejects_non_positive_amount(tmp_path):
    invalid = mutate_workbook_in_zip(
        make_ledger_zip(tmp_path), tmp_path,
        lambda workbook: setattr(workbook["费用明细"]["I4"], "value", 0),
    )
    with pytest.raises(ValueError, match="金额无效"):
        parse_ledger_source(invalid)


def test_parser_rejects_duplicate_record_id(tmp_path):
    invalid = mutate_workbook_in_zip(
        make_ledger_zip(tmp_path), tmp_path,
        lambda workbook: append_detail_copy(workbook),
    )
    with pytest.raises(ValueError, match="重复记录编号"):
        parse_ledger_source(invalid)
```

- [ ] **Step 2: Run the parser tests and verify the module is absent**

Run:

```bash
.venv/bin/pytest tests/test_ledger_import.py -q
```

Expected: FAIL because `construction_maintenance.services.ledger_import` does not exist.

- [ ] **Step 3: Add typed parser records and preview totals**

Create `construction_maintenance/services/ledger_import.py` with immutable dataclasses:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
import math
from pathlib import Path
from pathlib import PurePosixPath
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
    pending_headers = _headers(pending_sheet, tuple(PENDING_HEADERS))
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
        source_row = int(_value(row, pending_headers, "原始行号"))
        project_names.add(project_name)
        key = (source_filename, source_sheet, source_row)
        if record_type == "有金额待复核":
            review_keys.add(key)
            continue
        if record_type != "缺少金额":
            raise ValueError(
                f"{workbook_name}/待确认清单/{excel_row}: 记录类型无效"
            )
        primary = str(_value(row, pending_headers, "当前一级分类") or "").strip()
        secondary = str(_value(row, pending_headers, "当前二级分类") or "").strip()
        if (primary, secondary) not in category_pairs:
            raise ValueError(
                f"{workbook_name}/待确认清单/{excel_row}: 分类不存在"
            )
        pending_items.append(PendingLedgerItem(
            project_name=project_name,
            item_date=_iso_date(
                _value(row, pending_headers, "发生日期"), field="发生日期"
            ),
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
    detail_headers = _headers(detail_sheet, tuple(DETAIL_HEADERS))
    entries: list[LedgerEntry] = []
    for excel_row, row in enumerate(
        detail_sheet.iter_rows(min_row=4, values_only=True), start=4
    ):
        record_id = str(_value(row, detail_headers, "记录编号") or "").strip()
        if not record_id:
            continue
        project_name = str(_value(row, detail_headers, "项目名称") or "").strip()
        project_names.add(project_name)
        transaction_type = str(
            _value(row, detail_headers, "收支类型") or ""
        ).strip()
        if transaction_type not in TRANSACTION_TYPES:
            raise ValueError(
                f"{workbook_name}/费用明细/{excel_row}: 收支类型无效"
            )
        primary = str(_value(row, detail_headers, "一级分类") or "").strip()
        secondary = str(_value(row, detail_headers, "二级分类") or "").strip()
        scope = category_pairs.get((primary, secondary))
        expected_scope = "支出" if transaction_type in {"支出", "冲减支出"} else transaction_type
        if scope != expected_scope:
            raise ValueError(
                f"{workbook_name}/费用明细/{excel_row}: 分类与收支类型不匹配"
            )
        amount = _value(row, detail_headers, "金额（元）")
        if not isinstance(amount, (int, float)) or not math.isfinite(float(amount)) or amount <= 0:
            raise ValueError(f"{workbook_name}/费用明细/{excel_row}: 金额无效")
        payment_status = str(
            _value(row, detail_headers, "支付状态") or ""
        ).strip()
        if payment_status not in PAYMENT_STATUSES:
            raise ValueError(
                f"{workbook_name}/费用明细/{excel_row}: 付款状态无效"
            )
        confidence = str(
            _value(row, detail_headers, "分类置信度") or ""
        ).strip()
        if confidence and confidence not in CLASSIFICATION_CONFIDENCES:
            raise ValueError(
                f"{workbook_name}/费用明细/{excel_row}: 分类置信度无效"
            )
        source_filename = str(
            _value(row, detail_headers, "来源文件") or ""
        ).strip()
        source_sheet = str(
            _value(row, detail_headers, "来源工作表") or ""
        ).strip()
        source_row = int(_value(row, detail_headers, "原始行号"))
        payment_date_value = _value(row, detail_headers, "支付日期")
        entries.append(LedgerEntry(
            source_record_id=record_id,
            project_name=project_name,
            entry_date=_iso_date(
                _value(row, detail_headers, "发生日期"), field="发生日期"
            ),
            transaction_type=transaction_type,
            primary_category=primary,
            secondary_category=secondary,
            summary=str(_value(row, detail_headers, "事项摘要") or "").strip(),
            amount=float(amount),
            handler_name=str(
                _value(row, detail_headers, "经办/垫付人") or ""
            ).strip(),
            payment_status=payment_status,
            payment_date=(
                _iso_date(payment_date_value, field="支付日期")
                if payment_date_value else ""
            ),
            payment_notes=str(
                _value(row, detail_headers, "支付/报销说明") or ""
            ).strip(),
            original_notes=str(
                _value(row, detail_headers, "备注（原始用途/购买原因）") or ""
            ).strip(),
            classification_confidence=confidence,
            source_filename=source_filename,
            source_sheet=source_sheet,
            source_row=source_row,
            review_status=(
                "待复核"
                if (source_filename, source_sheet, source_row) in review_keys
                else "已确认"
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
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise ValueError(f"不安全的压缩包路径: {member.filename}")
                    if member.is_dir() or len(member_path.parts) != 1:
                        continue
                    if member_path.suffix.lower() == ".xlsx":
                        workbook_sources.append(
                            (member_path.name, BytesIO(archive.read(member)))
                        )
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
        parsed_entries, parsed_pending, parsed_projects = _parse_workbook(
            workbook, workbook_name
        )
        for entry in parsed_entries:
            if entry.source_record_id in record_ids:
                raise ValueError(f"重复记录编号: {entry.source_record_id}")
            record_ids.add(entry.source_record_id)
        entries.extend(parsed_entries)
        pending_items.extend(parsed_pending)
        projects.update(parsed_projects)

    totals = {
        "expense": sum(e.amount for e in entries if e.transaction_type == "支出"),
        "expense_reduction": sum(
            e.amount for e in entries if e.transaction_type == "冲减支出"
        ),
        "income": sum(e.amount for e in entries if e.transaction_type == "收入"),
        "fund_transfer": sum(
            e.amount for e in entries if e.transaction_type == "资金往来"
        ),
    }
    totals["net_expense"] = totals["expense"] - totals["expense_reduction"]
    return LedgerImportPreview(
        project_names=tuple(sorted(projects)),
        entries=tuple(entries),
        pending_items=tuple(pending_items),
        totals=totals,
    )
```

- [ ] **Step 4: Implement safe ZIP/XLSX loading and validation**

`parse_ledger_source(path)` must:

1. Accept `.zip` or `.xlsx` only.
2. Reject absolute and parent-traversal ZIP member names.
3. Parse only top-level `.xlsx` members.
4. Require `费用明细` and `待确认清单`.
5. Validate transaction type, payment status, classification confidence, project name, date, amount, and category pair against `finance.py`.
6. Match “有金额待复核” rows to formal rows by `(来源文件, 来源工作表, 原始行号)`.
7. Keep only “缺少金额” rows in `pending_items`.
8. Raise one `ValueError` containing the workbook name, sheet, and row for the first invalid input.

- [ ] **Step 5: Run parser tests**

Run:

```bash
.venv/bin/pytest tests/test_ledger_import.py -q
```

Expected: PASS for the representative workbook and all rejection cases.

- [ ] **Step 6: Commit the parser**

Run:

```bash
git add construction_maintenance/services/ledger_import.py tests/test_ledger_import.py
git commit -m "feat: parse standard project ledgers"
```

### Task 5: Add Idempotent Import, Exact Demo Cleanup, And Flask CLI

**Files:**
- Modify: `construction_maintenance/services/ledger_import.py`
- Create: `construction_maintenance/commands.py`
- Modify: `construction_maintenance/app.py:10-18,39-64`
- Modify: `tests/test_ledger_import.py`

- [ ] **Step 1: Write failing dry-run, cleanup-isolation, import, and idempotency tests**

Add these imports and tests to `tests/test_ledger_import.py`:

```python
from construction_maintenance import create_app
from construction_maintenance.db import get_db
from construction_maintenance.services.ledger_import import apply_ledger_import

PROTECTED_TABLES = ("companies", "people", "qualifications", "attendance")


def counts(db, tables):
    return {
        table: db.execute(f"select count(*) from {table}").fetchone()[0]
        for table in tables
    }


def make_seeded_app(tmp_path):
    return create_app({
        "TESTING": True,
        "DATABASE": tmp_path / "seeded.sqlite3",
        "UPLOAD_FOLDER": tmp_path / "uploads",
        "AUTH_REQUIRED": False,
        "CSRF_ENABLED": False,
        "SEED_DEMO_DATA": True,
    })


def test_parse_preview_does_not_write_database(tmp_path):
    app = make_seeded_app(tmp_path)
    with app.app_context():
        before = counts(get_db(), ("projects", "vouchers", "contracts"))
        parse_ledger_source(make_ledger_zip(tmp_path))
        after = counts(get_db(), ("projects", "vouchers", "contracts"))
    assert after == before


def test_apply_replaces_only_demo_projects_and_is_idempotent(tmp_path):
    app = make_seeded_app(tmp_path)
    preview = parse_ledger_source(make_ledger_zip(tmp_path))
    with app.app_context():
        db = get_db()
        protected_before = counts(db, PROTECTED_TABLES)
        first = apply_ledger_import(
            preview, replace_demo_projects=True, actor_admin_id=None
        )
        protected_after = counts(db, PROTECTED_TABLES)
        demo_projects = db.execute(
            "select count(*) from projects where name in ('中央电视总台项目', '军庄项目')"
        ).fetchone()[0]
        imported = counts(db, ("projects", "vouchers", "contracts", "ledger_pending_items"))
        second = apply_ledger_import(
            preview, replace_demo_projects=True, actor_admin_id=None
        )
        repeated = counts(db, ("projects", "vouchers", "contracts", "ledger_pending_items"))

    assert protected_after == protected_before
    assert demo_projects == 0
    assert first["projects"] == 1
    assert first["entries"] == 1
    assert first["pending_items"] == 1
    assert imported == {
        "projects": 1, "vouchers": 1, "contracts": 0,
        "ledger_pending_items": 1,
    }
    assert second["entries"] == 0
    assert second["pending_items"] == 0
    assert repeated == imported


def test_cli_defaults_to_dry_run(tmp_path):
    app = make_seeded_app(tmp_path)
    source = make_ledger_zip(tmp_path)
    result = app.test_cli_runner().invoke(args=["ledger-import", str(source)])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    assert "entries=1" in result.output
```

- [ ] **Step 2: Run focused tests and verify import functions are missing**

Run:

```bash
.venv/bin/pytest tests/test_ledger_import.py -q
```

Expected: FAIL on missing `apply_ledger_import` and CLI command.

- [ ] **Step 3: Add an exact seed manifest and guarded cleanup**

In `ledger_import.py`, define the exact project seed manifest from `db.py`, including project name, owner, start/end dates, and notes. `_delete_verified_demo_projects(db)` must query each matching project and abort unless all stored identifying fields match the manifest. It must then delete only contracts and vouchers for those verified IDs, followed by those project IDs. It must not execute `delete from projects` without an ID predicate.

Use this manifest and guard:

```python
DEMO_PROJECTS = {
    "中央电视总台项目": ("进行中", "中央电视台", "2026-01-01", "2026-12-31", "包含中央电视总台项目资料"),
    "军庄项目": ("进行中", "军庄建设方", "2026-02-01", "2026-12-31", "包含军庄资料"),
    "衙门口项目": ("进行中", "衙门口建设方", "2026-03-01", "2026-12-31", "包含衙门口资料"),
    "老东山项目": ("已完工", "老东山建设方", "2025-05-01", "2026-05-01", "老东山资料-完工"),
    "通州潞城项目": ("进行中", "通州区潞城建设", "2026-04-01", "2026-12-31", "通州潞城项目资料"),
    "内蒙二期项目": ("已完工", "内蒙电力", "2025-06-01", "2026-05-01", "内蒙二期项目-完工"),
    "首师大八里庄项目": ("进行中", "首师大", "2026-04-15", "2026-12-31", "首师大八里庄项目资料"),
    "北理工项目": ("已完工", "北京理工大学", "2025-07-01", "2026-05-01", "北理工项目-完工"),
    "顺义项目": ("进行中", "顺义建设方", "2026-05-01", "2026-12-31", "顺义项目资料"),
    "通州六合工地项目": ("进行中", "通州区六合", "2026-03-10", "2026-12-31", "通州六合工地"),
    "新兴项目": ("进行中", "新兴建设方", "2026-02-15", "2026-12-31", "新兴资料"),
    "梧桐苑项目": ("进行中", "梧桐苑房地产", "2026-01-10", "2026-12-31", "梧桐苑项目资料"),
}
DEMO_VOUCHERS = {
    ("中央电视总台项目", "2026-05-20", "材料费用", 15200.0, "中央电视总台项目采购电缆一批"),
    ("军庄项目", "2026-05-24", "转账凭证", 4800.0, "军庄项目 - 运输运费报销"),
    ("中央电视总台项目", "2026-05-28", "油费", 2400.0, "项目车辆5月油卡充值报销凭证"),
}
DEMO_CONTRACTS = {
    ("中央电视总台项目", "中央电视总台项目劳务分包合同", "劳务合同", "contract_metro_labor.pdf"),
    ("军庄项目", "军庄项目绿化苗木采购合同", "材料商合同", "contract_green_tree.pdf"),
}


def _delete_verified_demo_projects(db) -> None:
    placeholders = ",".join("?" for _ in DEMO_PROJECTS)
    projects = db.execute(
        f"select * from projects where name in ({placeholders})",
        tuple(DEMO_PROJECTS),
    ).fetchall()
    if {row["name"] for row in projects} != set(DEMO_PROJECTS):
        raise ValueError("演示项目清单与生产库不一致，停止清理")
    for row in projects:
        actual = (
            row["status"], row["owner"], row["start_date"],
            row["end_date"], row["notes"],
        )
        if actual != DEMO_PROJECTS[row["name"]]:
            raise ValueError(f"项目 {row['name']} 已被修改，停止清理")
    project_ids = {int(row["id"]): row["name"] for row in projects}
    id_placeholders = ",".join("?" for _ in project_ids)
    vouchers = db.execute(
        f"""
        select project_id, voucher_date, voucher_type, amount, notes
        from vouchers where project_id in ({id_placeholders})
        """,
        tuple(project_ids),
    ).fetchall()
    voucher_manifest = {
        (project_ids[int(row["project_id"])], row["voucher_date"], row["voucher_type"],
         float(row["amount"]), row["notes"])
        for row in vouchers
    }
    contracts = db.execute(
        f"""
        select project_id, name, contract_type, attachment_path
        from contracts where project_id in ({id_placeholders})
        """,
        tuple(project_ids),
    ).fetchall()
    contract_manifest = {
        (project_ids[int(row["project_id"])], row["name"], row["contract_type"],
         row["attachment_path"])
        for row in contracts
    }
    if voucher_manifest != DEMO_VOUCHERS or contract_manifest != DEMO_CONTRACTS:
        raise ValueError("演示项目下存在非演示财务数据，停止清理")
    db.execute(
        f"delete from contracts where project_id in ({id_placeholders})",
        tuple(project_ids),
    )
    db.execute(
        f"delete from vouchers where project_id in ({id_placeholders})",
        tuple(project_ids),
    )
    db.execute(
        f"delete from projects where id in ({id_placeholders})",
        tuple(project_ids),
    )
```

- [ ] **Step 4: Implement the one-transaction importer**

Add:

```python
def apply_ledger_import(
    preview: LedgerImportPreview,
    *,
    replace_demo_projects: bool,
    actor_admin_id: int | None,
) -> dict[str, int | float]:
    from construction_maintenance import repositories as repo
    from construction_maintenance.db import get_db

    db = get_db()
    db.execute("begin immediate")
    try:
        if replace_demo_projects:
            demo_count = db.execute(
                f"select count(*) from projects where name in ({','.join('?' for _ in DEMO_PROJECTS)})",
                tuple(DEMO_PROJECTS),
            ).fetchone()[0]
            if demo_count:
                _delete_verified_demo_projects(db)
        main_company = db.execute(
            "select id from companies where is_main = 1 order by id limit 1"
        ).fetchone()
        if main_company is None:
            raise ValueError("生产库没有主公司，不能创建项目")
        category_ids = {
            (row["primary_name"], row["secondary_name"]): int(row["id"])
            for row in db.execute(
                """
                select leaf.id, leaf.name as secondary_name, parent.name as primary_name
                from expense_categories leaf
                join expense_categories parent on parent.id = leaf.parent_id
                where leaf.is_active = 1 and parent.is_active = 1
                """
            ).fetchall()
        }
        project_ids: dict[str, int] = {}
        for project_name in preview.project_names:
            existing = db.execute(
                "select id from projects where name = ?", (project_name,)
            ).fetchone()
            if existing:
                project_ids[project_name] = int(existing["id"])
                continue
            project_entries = [
                entry for entry in preview.entries if entry.project_name == project_name
            ]
            start_date = min(entry.entry_date for entry in project_entries)
            end_of_source_period = max(entry.entry_date for entry in project_entries)
            cursor = db.execute(
                """
                insert into projects (
                  company_id, name, status, owner, start_date, end_date, notes
                ) values (?, ?, '进行中', '', ?, '', ?)
                """,
                (
                    int(main_company["id"]),
                    project_name,
                    start_date,
                    f"标准账套导入；账目期间 {start_date} 至 {end_of_source_period}",
                ),
            )
            project_ids[project_name] = int(cursor.lastrowid)

        inserted_entries = 0
        for entry in preview.entries:
            exists = db.execute(
                "select 1 from vouchers where source_record_id = ?",
                (entry.source_record_id,),
            ).fetchone()
            if exists:
                continue
            category_id = category_ids.get(
                (entry.primary_category, entry.secondary_category)
            )
            if category_id is None:
                raise ValueError(
                    f"分类不存在: {entry.primary_category}/{entry.secondary_category}"
                )
            repo._insert_voucher(db, {
                "project_id": project_ids[entry.project_name],
                "voucher_date": entry.entry_date,
                "transaction_type": entry.transaction_type,
                "category_id": category_id,
                "amount": entry.amount,
                "notes": entry.summary,
                "handler_name": entry.handler_name,
                "payment_status": entry.payment_status,
                "payment_date": entry.payment_date,
                "payment_notes": entry.payment_notes,
                "review_status": entry.review_status,
                "classification_confidence": entry.classification_confidence,
                "source_record_id": entry.source_record_id,
                "source_filename": entry.source_filename,
                "source_sheet": entry.source_sheet,
                "source_row": entry.source_row,
                "original_notes": entry.original_notes,
                "entry_user": "账套导入",
            })
            inserted_entries += 1

        inserted_pending = 0
        for item in preview.pending_items:
            category_id = category_ids.get(
                (item.primary_category, item.secondary_category)
            )
            if category_id is None:
                raise ValueError(
                    f"分类不存在: {item.primary_category}/{item.secondary_category}"
                )
            cursor = db.execute(
                """
                insert or ignore into ledger_pending_items (
                  project_id, item_date, summary, suggested_category_id,
                  handler_name, payment_notes, source_filename, source_sheet,
                  source_row, issue_type
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_ids[item.project_name], item.item_date, item.summary,
                    category_id, item.handler_name, item.payment_notes,
                    item.source_filename, item.source_sheet, item.source_row,
                    item.issue_type,
                ),
            )
            inserted_pending += int(cursor.rowcount > 0)
        repo._insert_audit(
            db,
            actor_admin_id=actor_admin_id,
            action="import",
            entity_type="project_ledger",
            entity_id=None,
            details={
                "projects": len(project_ids),
                "entries": inserted_entries,
                "pending_items": inserted_pending,
                "totals": preview.totals,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "projects": len(project_ids),
        "entries": inserted_entries,
        "pending_items": inserted_pending,
        **preview.totals,
    }
```

The explicit source-ID check plus the unique index makes formal imports idempotent. `insert or ignore` plus the pending table’s unique source tuple makes missing-amount rows idempotent. Exact project names prevent duplicates; imported projects use the source minimum date, blank owner/end date, `进行中`, and a deterministic source-period note.

- [ ] **Step 5: Register a safe-by-default Flask CLI**

Create `construction_maintenance/commands.py`:

```python
from __future__ import annotations

from pathlib import Path

import click

from .services.ledger_import import apply_ledger_import, parse_ledger_source


def init_app(app) -> None:
    @app.cli.command("ledger-import")
    @click.argument("source", type=click.Path(exists=True, path_type=Path))
    @click.option("--apply", "apply_changes", is_flag=True, default=False)
    @click.option("--replace-demo-projects", is_flag=True, default=False)
    def ledger_import(source: Path, apply_changes: bool, replace_demo_projects: bool):
        preview = parse_ledger_source(source)
        click.echo("APPLY" if apply_changes else "DRY RUN")
        click.echo(f"projects={preview.project_count}")
        click.echo(f"entries={len(preview.entries)}")
        click.echo(f"pending_items={len(preview.pending_items)}")
        for key, value in preview.totals.items():
            click.echo(f"{key}={value:.2f}")
        if apply_changes:
            result = apply_ledger_import(
                preview,
                replace_demo_projects=replace_demo_projects,
                actor_admin_id=None,
            )
            click.echo(f"inserted_entries={result['entries']}")
```

Import and call `commands.init_app(app)` after database initialization in `create_app()`.

- [ ] **Step 6: Run importer and CLI tests**

Run:

```bash
.venv/bin/pytest tests/test_ledger_import.py -q
```

Expected: PASS, including preservation, rollback, and repeat-import cases.

- [ ] **Step 7: Commit the importer**

Run:

```bash
git add construction_maintenance/services/ledger_import.py construction_maintenance/commands.py construction_maintenance/app.py tests/test_ledger_import.py
git commit -m "feat: import project ledgers idempotently"
```

### Task 6: Align Dashboard And Excel Export With Financial Semantics

**Files:**
- Modify: `construction_maintenance/services/dashboard.py`
- Modify: `construction_maintenance/services/exports.py:92-114`
- Modify: `construction_maintenance/templates/dashboard.html`
- Create: `tests/test_financial_reporting.py`
- Modify: `tests/test_dashboard.py`
- Modify: `tests/test_exports.py`

- [ ] **Step 1: Write failing reporting tests**

Create `tests/test_financial_reporting.py` with four entries (expense 1000, reduction 100, income 50, fund transfer 200) and assert:

```python
dashboard = build_dashboard()
assert dashboard["expense"] == 1000
assert dashboard["expense_reduction"] == 100
assert dashboard["net_expense"] == 900
assert dashboard["income"] == 50
assert dashboard["fund_transfer"] == 200
```

Export the project ledger and assert the first sheet headers equal:

```python
[
    "记录编号", "日期", "项目", "收支类型", "一级分类", "二级分类",
    "事项摘要", "金额", "经办/垫付人", "付款状态", "付款日期",
    "支付/报销说明", "复核状态", "分类置信度", "来源文件",
    "来源工作表", "原始行号", "作废状态",
]
```

Also assert formula-like source text is escaped by `safe_excel_value`.

- [ ] **Step 2: Run reporting tests and verify old totals fail**

Run:

```bash
.venv/bin/pytest tests/test_financial_reporting.py tests/test_dashboard.py tests/test_exports.py -q
```

Expected: FAIL because the current dashboard sums every amount as spending and the export has seven legacy columns.

- [ ] **Step 3: Replace dashboard totals with transaction-aware SQL**

Update `build_dashboard()` to exclude voided rows and return `expense`, `expense_reduction`, `net_expense`, `income`, and `fund_transfer`. Keep the legacy `total_spending` key temporarily equal to `net_expense` so unrelated templates/tests remain compatible during the same release.

- [ ] **Step 4: Expand the project-ledger export**

Update `PROJECT_LEDGER_HEADERS` to the exact list in Step 1. Populate each row from joined category names and structured voucher fields. Apply `safe_excel_value` to every string field, set date and currency number formats, freeze the header row, enable filters, and size columns to bounded readable widths.

- [ ] **Step 5: Update dashboard labels**

In `dashboard.html`, label project cost as “项目净支出” and add compact secondary metrics for income and funds movement. Do not count pending items as financial entries.

- [ ] **Step 6: Run reporting regression tests**

Run:

```bash
.venv/bin/pytest tests/test_financial_reporting.py tests/test_dashboard.py tests/test_exports.py -q
```

Expected: PASS with the approved financial semantics.

- [ ] **Step 7: Commit reporting**

Run:

```bash
git add construction_maintenance/services/dashboard.py construction_maintenance/services/exports.py construction_maintenance/templates/dashboard.html tests/test_financial_reporting.py tests/test_dashboard.py tests/test_exports.py
git commit -m "feat: report project finance by transaction type"
```

### Task 7: Upgrade Ledger, Category, And Pending-Item Pages

**Files:**
- Modify: `construction_maintenance/web/routes.py:57-64,290-498,1443-1471`
- Modify: `construction_maintenance/templates/project_vouchers.html`
- Modify: `construction_maintenance/templates/vouchers.html`
- Modify: `construction_maintenance/templates/expense_categories.html`
- Create: `construction_maintenance/templates/ledger_pending.html`
- Modify: `construction_maintenance/static/app.css`
- Create: `tests/test_ledger_routes.py`
- Modify: `tests/test_routes.py`

- [ ] **Step 1: Write failing route tests**

Create `tests/test_ledger_routes.py` and assert:

```python
import pytest

from construction_maintenance import repositories as repo
from construction_maintenance.db import get_db


def seed_structured_financial_entry(app):
    with app.app_context():
        company = repo.get_main_company()
        project_id = repo.create_project({
            "company_id": company["id"], "name": "页面测试项目"
        })
        category = get_db().execute(
            """
            select leaf.id, leaf.parent_id
            from expense_categories leaf
            where leaf.name = '五金辅材及工具'
            """
        ).fetchone()
        repo.create_voucher({
            "project_id": project_id,
            "voucher_date": "2026-07-01",
            "transaction_type": "支出",
            "category_id": category["id"],
            "amount": 100,
            "payment_status": "未支付",
            "review_status": "待复核",
        })
        return {
            "project_id": project_id,
            "category_id": int(category["id"]),
            "primary_id": int(category["parent_id"]),
        }


def seed_pending_item(app):
    with app.app_context():
        company = repo.get_main_company()
        project_id = repo.create_project({
            "company_id": company["id"], "name": "待补录页面测试"
        })
        category_id = int(get_db().execute(
            "select id from expense_categories where name = '运输车辆台班'"
        ).fetchone()["id"])
        item_id = repo.create_ledger_pending_item({
            "project_id": project_id,
            "item_date": "2026-03-17",
            "summary": "大车两个台班",
            "suggested_category_id": category_id,
            "source_filename": "source.xls",
            "source_sheet": "汇总",
            "source_row": 7,
            "issue_type": "缺少金额",
        })
        return project_id, item_id, category_id


def test_project_ledger_renders_structured_filters_and_summary(client, app):
    seeded = seed_structured_financial_entry(app)
    response = client.get(
        f"/projects/{seeded['project_id']}/vouchers?transaction_type=支出&payment_status=未支付"
    )
    assert response.status_code == 200
    assert "项目净支出".encode() in response.data
    assert "一级分类".encode() in response.data
    assert "未支付".encode() in response.data


def test_pending_item_can_be_completed(client, app):
    project_id, item_id, category_id = seed_pending_item(app)
    response = client.post(
        f"/ledger-pending/{item_id}/complete",
        data={
            "amount": "1200",
            "transaction_type": "支出",
            "category_id": str(category_id),
            "payment_status": "支付状态待确认",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "已转正式明细".encode() in response.data


def test_all_ledger_filters_keep_the_matching_entry(client, app):
    seeded = seed_structured_financial_entry(app)
    queries = [
        "transaction_type=支出",
        f"primary_category_id={seeded['primary_id']}",
        f"category_id={seeded['category_id']}",
        "payment_status=未支付",
        "review_status=待复核",
        "date_from=2026-07-01&date_to=2026-07-01",
    ]
    for query in queries:
        response = client.get(
            f"/projects/{seeded['project_id']}/vouchers?{query}"
        )
        assert response.status_code == 200
        assert "100.00".encode() in response.data


def test_route_rejects_category_scope_mismatch(client, app):
    seeded = seed_structured_financial_entry(app)
    response = client.post(
        "/vouchers",
        data={
            "project_id": seeded["project_id"],
            "voucher_date": "2026-07-02",
            "transaction_type": "收入",
            "category_id": seeded["category_id"],
            "amount": "50",
            "payment_status": "已支付/已报销",
        },
    )
    assert response.status_code == 400
    assert "分类与收支类型不匹配".encode() in response.data


def test_route_rejects_inactive_leaf(client, app):
    seeded = seed_structured_financial_entry(app)
    with app.app_context():
        get_db().execute(
            "update expense_categories set is_active = 0 where id = ?",
            (seeded["category_id"],),
        )
        get_db().commit()
    response = client.post(
        "/vouchers",
        data={
            "project_id": seeded["project_id"],
            "voucher_date": "2026-07-02",
            "transaction_type": "支出",
            "category_id": seeded["category_id"],
            "amount": "50",
            "payment_status": "未支付",
        },
    )
    assert response.status_code == 400
    assert "二级分类不存在或已停用".encode() in response.data


def test_category_migration_route_moves_existing_entry(client, app):
    seeded = seed_structured_financial_entry(app)
    with app.app_context():
        target_id = int(get_db().execute(
            "select id from expense_categories where name = '电气材料'"
        ).fetchone()["id"])
    response = client.post(
        f"/expense-categories/{seeded['category_id']}/migrate",
        data={"target_id": str(target_id)},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        source_active = get_db().execute(
            "select is_active from expense_categories where id = ?",
            (seeded["category_id"],),
        ).fetchone()["is_active"]
        voucher_category = get_db().execute(
            "select category_id from vouchers where project_id = ?",
            (seeded["project_id"],),
        ).fetchone()["category_id"]
    assert source_active == 0
    assert voucher_category == target_id
```

- [ ] **Step 2: Run route tests and verify the pages lack structured controls**

Run:

```bash
.venv/bin/pytest tests/test_ledger_routes.py -q
```

Expected: FAIL because structured filters and pending routes do not exist.

- [ ] **Step 3: Wire structured create/edit and filter routes**

Update voucher POST handlers to read:

```python
{
    "project_id": int(required_text(request.form, "project_id", "项目")),
    "voucher_date": required_text(request.form, "voucher_date", "日期"),
    "transaction_type": required_text(request.form, "transaction_type", "收支类型"),
    "category_id": int(required_text(request.form, "category_id", "二级分类")),
    "amount": required_text(request.form, "amount", "金额"),
    "notes": text_value(request.form, "notes"),
    "handler_name": text_value(request.form, "handler_name"),
    "payment_status": required_text(request.form, "payment_status", "付款状态"),
    "payment_date": text_value(request.form, "payment_date"),
    "payment_notes": text_value(request.form, "payment_notes"),
    "review_status": text_value(request.form, "review_status") or "已确认",
    "actor_admin_id": _actor_id(),
}
```

Pass query filters to `repo.list_vouchers()` and pass `repo.get_project_financial_summary()` plus the category tree to the templates.

- [ ] **Step 4: Add pending list and completion routes**

Add these routes:

```python
@bp.get("/ledger-pending")
def ledger_pending():
    project_id = request.args.get("project_id", type=int)
    status = request.args.get("status", "待补录").strip()
    if status not in {"待补录", "已转正式明细", "已忽略"}:
        raise ValueError("待补录状态无效")
    return render_template(
        "ledger_pending.html",
        items=repo.list_ledger_pending_items(project_id=project_id, status=status),
        projects=repo.list_projects(),
        categories=repo.list_expense_categories(include_inactive=False),
        filter_project_id=project_id,
        filter_status=status,
    )


@bp.post("/ledger-pending/<int:item_id>/complete")
def complete_ledger_pending(item_id: int):
    repo.convert_ledger_pending_item(
        item_id,
        amount=required_text(request.form, "amount", "金额"),
        category_id=int(required_text(request.form, "category_id", "二级分类")),
        transaction_type=required_text(request.form, "transaction_type", "收支类型"),
        payment_status=required_text(request.form, "payment_status", "付款状态"),
        actor_admin_id=_actor_id(),
    )
    flash("待补录事项已转正式明细。", "success")
    return redirect(url_for("web.ledger_pending", status="已转正式明细"))


@bp.post("/ledger-pending/<int:item_id>/ignore")
def ignore_ledger_pending(item_id: int):
    repo.ignore_ledger_pending_item(item_id, actor_admin_id=_actor_id())
    flash("待补录事项已忽略。", "success")
    return redirect(url_for("web.ledger_pending", status="待补录"))


@bp.post("/expense-categories/<int:category_id>/migrate")
def migrate_expense_category(category_id: int):
    target_id = int(required_text(request.form, "target_id", "目标分类"))
    repo.migrate_expense_category(
        category_id, target_id, actor_admin_id=_actor_id()
    )
    flash("分类引用已迁移，原分类已停用。", "success")
    return redirect(url_for("web.expense_categories"))
```

- [ ] **Step 5: Replace flat category management with a tree**

Render root rows with their child rows. Root forms edit name, scope, order, and active state. Child forms edit name, parent, order, and active state. Show a “迁移并停用” action only when a category has references; require an explicit target leaf and server-side scope validation.

- [ ] **Step 6: Update project and global ledger templates**

Use a stable two-row filter band with native `<select>` controls. Display the seven approved KPIs. In create/edit forms, embed the category tree as JSON and filter the secondary `<select>` when the primary selection changes:

```javascript
function syncSecondaryCategories(primarySelect, secondarySelect, categories) {
  const parentId = Number(primarySelect.value);
  secondarySelect.replaceChildren();
  categories
    .filter((item) => item.parent_id === parentId && item.is_active)
    .forEach((item) => secondarySelect.add(new Option(item.name, String(item.id))));
}
```

Keep icon buttons and tooltips consistent with `_icons.html`. Do not add nested cards; KPI bands and filters stay unframed within the existing page content.

- [ ] **Step 7: Add the pending template and focused responsive CSS**

`ledger_pending.html` renders source/date/project/summary/suggested category and a completion form. In `app.css`, add stable grid tracks for the filter band and pending actions, then collapse to one column below the existing tablet breakpoint. Ensure buttons and select labels wrap without overlap.

- [ ] **Step 8: Run route and UI-source tests**

Run:

```bash
.venv/bin/pytest tests/test_ledger_routes.py tests/test_routes.py tests/test_ui_theme.py tests/test_icon_assets.py -q
```

Expected: PASS; all forms include CSRF fields through the existing template pattern.

- [ ] **Step 9: Commit the UI unit**

Run:

```bash
git add construction_maintenance/web/routes.py construction_maintenance/templates/project_vouchers.html construction_maintenance/templates/vouchers.html construction_maintenance/templates/expense_categories.html construction_maintenance/templates/ledger_pending.html construction_maintenance/static/app.css tests/test_ledger_routes.py tests/test_routes.py
git commit -m "feat: add structured project ledger workflow"
```

### Task 8: Verify Against The Real ZIP And Create The Production Runbook

**Files:**
- Create: `docs/runbooks/2026-07-26-project-ledger-production-import.md`
- Create: `scripts/verify_ledger_import_copy.py`
- Modify: `deploy/nginx-pam.conf.example`
- Test: all `tests/`

- [ ] **Step 1: Run the complete automated suite**

Run:

```bash
.venv/bin/pytest -q
```

Expected: all tests pass; no failure or error is accepted.

- [ ] **Step 2: Run a dry-run against the real source archive**

Run:

```bash
.venv/bin/flask --app construction_maintenance ledger-import '/Users/rylinx/Downloads/各项目独立账套_汇总.zip'
```

Expected output contains:

```text
DRY RUN
projects=6
entries=4907
pending_items=276
expense=11643311.78
expense_reduction=17573.00
net_expense=11625738.78
income=43670.00
fund_transfer=50128.83
```

- [ ] **Step 3: Import into a copy of the production database**

Create `scripts/verify_ledger_import_copy.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from construction_maintenance import create_app
from construction_maintenance.db import get_db
from construction_maintenance.services.ledger_import import (
    apply_ledger_import,
    parse_ledger_source,
)

PROTECTED_TABLES = (
    "companies", "people", "qualifications", "attendance",
    "salary_payments", "salary_sheets", "admin_users", "system_settings",
)
EXPECTED = {
    "projects": 6,
    "entries": 4907,
    "review_entries": 483,
    "pending_items": 276,
    "expense": 11_643_311.78,
    "expense_reduction": 17_573.00,
    "net_expense": 11_625_738.78,
    "income": 43_670.00,
    "fund_transfer": 50_128.83,
}


def table_counts(db) -> dict[str, int]:
    return {
        table: int(db.execute(f"select count(*) from {table}").fetchone()[0])
        for table in PROTECTED_TABLES
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    app = create_app({
        "TESTING": True,
        "AUTH_REQUIRED": False,
        "CSRF_ENABLED": False,
        "SEED_DEMO_DATA": False,
        "DATABASE": args.database,
        "UPLOAD_FOLDER": args.database.parent / "verify-uploads",
    })
    preview = parse_ledger_source(args.source)
    with app.app_context():
        db = get_db()
        protected_before = table_counts(db)
        apply_ledger_import(
            preview, replace_demo_projects=True, actor_admin_id=None
        )
        protected_after = table_counts(db)
        if protected_after != protected_before:
            raise AssertionError({
                "protected_before": protected_before,
                "protected_after": protected_after,
            })
        counts = {
            "projects": db.execute(
                f"select count(*) from projects where name in ({','.join('?' for _ in preview.project_names)})",
                preview.project_names,
            ).fetchone()[0],
            "entries": db.execute(
                "select count(*) from vouchers where source_record_id is not null and is_void = 0"
            ).fetchone()[0],
            "review_entries": db.execute(
                "select count(*) from vouchers where review_status = '待复核' and is_void = 0"
            ).fetchone()[0],
            "pending_items": db.execute(
                "select count(*) from ledger_pending_items where status = '待补录'"
            ).fetchone()[0],
        }
        amounts = {
            row["transaction_type"]: float(row["amount"])
            for row in db.execute(
                """
                select transaction_type, round(sum(amount), 2) as amount
                from vouchers
                where source_record_id is not null and is_void = 0
                group by transaction_type
                """
            ).fetchall()
        }
        actual = {
            **counts,
            "expense": amounts.get("支出", 0.0),
            "expense_reduction": amounts.get("冲减支出", 0.0),
            "net_expense": amounts.get("支出", 0.0) - amounts.get("冲减支出", 0.0),
            "income": amounts.get("收入", 0.0),
            "fund_transfer": amounts.get("资金往来", 0.0),
        }
        if actual != EXPECTED:
            raise AssertionError({"expected": EXPECTED, "actual": actual})
        second = apply_ledger_import(
            preview, replace_demo_projects=True, actor_admin_id=None
        )
        if second["entries"] != 0 or second["pending_items"] != 0:
            raise AssertionError({"second_import": second})
    print(json.dumps({"protected": protected_after, "import": actual}, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

Copy and verify with exact commands:

```bash
pam_verify_dir=$(mktemp -d /tmp/pam-ledger-verify.XXXXXX)
scp root@192.144.171.234:/root/cam/instance/construction.sqlite3 "$pam_verify_dir/construction.sqlite3"
.venv/bin/python scripts/verify_ledger_import_copy.py \
  --database "$pam_verify_dir/construction.sqlite3" \
  --source '/Users/rylinx/Downloads/各项目独立账套_汇总.zip'
```

Expected: one JSON object containing unchanged protected counts and the exact approved import values.

Run the following read-only acceptance query against the imported copy:

```sql
select transaction_type, count(*) as records, round(sum(amount), 2) as amount
from vouchers
where is_void = 0
group by transaction_type
order by transaction_type;

select count(*) as review_entries
from vouchers
where review_status = '待复核' and is_void = 0;

select count(*) as pending_items
from ledger_pending_items
where status = '待补录';
```

Expected: 4,907 formal entries, 483 review entries, 276 pending items, and the approved totals.

- [ ] **Step 4: Start the local server and run browser verification**

Run:

```bash
CAM_AUTH_REQUIRED=0 CAM_SESSION_COOKIE_SECURE=0 .venv/bin/flask --app construction_maintenance run --host 127.0.0.1 --port 5001
```

Use the Browser skill to verify dashboard, project list, one populated project ledger, all filter combinations, category management, pending completion, and Excel download. Capture desktop `1440x900` and mobile `390x844` screenshots; verify no overlapping labels, controls, tables, modals, or buttons.

- [ ] **Step 5: Write the exact production runbook**

Create `docs/runbooks/2026-07-26-project-ledger-production-import.md` with the commands in Task 9, the expected source totals, the preservation queries, the rollback trigger, and the backup paths. Do not include passwords, session secrets, or password hashes.

- [ ] **Step 6: Harden the Nginx example**

Ensure `deploy/nginx-pam.conf.example` contains:

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
client_max_body_size 20m;
proxy_connect_timeout 60s;
proxy_send_timeout 120s;
proxy_read_timeout 120s;
```

- [ ] **Step 7: Commit verification and runbook files**

Run:

```bash
git add docs/runbooks/2026-07-26-project-ledger-production-import.md deploy/nginx-pam.conf.example scripts/verify_ledger_import_copy.py
git commit -m "docs: add project ledger production runbook"
```

### Task 9: Back Up, Deploy, Import, And Verify Production

**Files/Systems:**
- Local release: `/Users/rylinx/Documents/ylt-PAM`
- Remote app: `/root/cam`
- Remote database: `/root/cam/instance/construction.sqlite3`
- Remote uploads: `/root/cam/uploads`
- Remote service: `cam.service`
- Remote Nginx site: `/www/server/panel/vhost/nginx/pam.etgq.com.conf`
- Source archive staging: `/root/cam-deploy/imports/各项目独立账套_汇总.zip`

- [ ] **Step 1: Record pre-deploy preservation counts**

Run the runbook’s read-only SQL and save counts for `companies`, `people`, `qualifications`, `attendance`, `salary_payments`, `salary_sheets`, `admin_users`, and `system_settings`. Also record the existing 12 projects, 3 vouchers, and 2 contracts.

- [ ] **Step 2: Stop writes and create recoverable backups**

On the remote host:

```bash
pam_release_stamp=$(date +%Y%m%d_%H%M%S)
mkdir -p "/root/cam-backups/${pam_release_stamp}"
systemctl stop cam.service
sqlite3 /root/cam/instance/construction.sqlite3 ".backup '/root/cam-backups/${pam_release_stamp}/construction.sqlite3'"
tar -C /root/cam -czf "/root/cam-backups/${pam_release_stamp}/uploads.tar.gz" uploads
tar -C /root -czf "/root/cam-backups/${pam_release_stamp}/cam-code.tar.gz" cam
```

Expected: all three backup artifacts exist and are non-empty before deployment continues.

- [ ] **Step 3: Stage the tested release without overwriting persistent data**

From the local workspace:

```bash
rsync -av \
  --exclude '.venv/' \
  --exclude 'instance/' \
  --exclude 'uploads/' \
  --exclude 'exports/' \
  --exclude '__pycache__/' \
  /Users/rylinx/Documents/ylt-PAM/ root@192.144.171.234:/root/cam/
ssh root@192.144.171.234 'mkdir -p /root/cam-deploy/imports'
scp '/Users/rylinx/Downloads/各项目独立账套_汇总.zip' 'root@192.144.171.234:/root/cam-deploy/imports/各项目独立账套_汇总.zip'
```

Expected: application source updates; `instance/`, `uploads/`, and `exports/` remain untouched.

- [ ] **Step 4: Install the release and run migration plus dry-run**

On the remote host:

```bash
cd /root/cam
.venv/bin/pip install -e .
.venv/bin/flask --app construction_maintenance ledger-import '/root/cam-deploy/imports/各项目独立账套_汇总.zip'
```

Expected: the dry-run output exactly matches Task 8 Step 2. No production ledger row has changed yet.

- [ ] **Step 5: Apply the single-transaction production import**

Run:

```bash
cd /root/cam
.venv/bin/flask --app construction_maintenance ledger-import '/root/cam-deploy/imports/各项目独立账套_汇总.zip' --apply --replace-demo-projects
```

Expected: 6 projects, 4,907 formal entries, 483 review entries, and 276 pending items. Any exception must leave the pre-import project/voucher/contract state unchanged through transaction rollback.

- [ ] **Step 6: Start the service and verify application health**

Run:

```bash
systemctl start cam.service
systemctl is-active cam.service
curl -fsS -o /dev/null -w '%{http_code}\n' https://pam.etgq.com/login
```

Expected: `active` and HTTP `200`.

- [ ] **Step 7: Apply and validate Nginx hardening**

On the remote host, use the same recorded `pam_release_stamp` from Step 2:

```bash
cp /www/server/panel/vhost/nginx/pam.etgq.com.conf \
  "/root/cam-backups/${pam_release_stamp}/pam.etgq.com.conf"
sed -i -E 's/^[[:space:]]*ssl_protocols .*/    ssl_protocols TLSv1.2 TLSv1.3;/' \
  /www/server/panel/vhost/nginx/pam.etgq.com.conf
if ! grep -q 'client_max_body_size 20m;' /www/server/panel/vhost/nginx/pam.etgq.com.conf; then
  sed -i '/server_name pam.etgq.com;/a\    client_max_body_size 20m;' \
    /www/server/panel/vhost/nginx/pam.etgq.com.conf
fi
nginx -t
systemctl reload nginx
```

Expected: Nginx configuration test succeeds before reload.

- [ ] **Step 8: Run preservation and financial acceptance queries**

Compare protected table counts to Step 1; they must be identical. Confirm:

```text
projects=6
vouchers=4907 active imported entries
review_entries=483
pending_items=276
expense=11643311.78
expense_reduction=17573.00
net_expense=11625738.78
income=43670.00
fund_transfer=50128.83
```

Also rerun the import command without `--apply` and confirm the preview remains identical.

- [ ] **Step 9: Run production smoke checks**

Verify the public login page, service logs, dashboard response, project ledger response, category tree, pending queue, and one project export. If no production application credentials are available, perform authenticated UI checks locally and report production browser authentication as the only unexecuted smoke check; do not reset an administrator password or forge a session.

- [ ] **Step 10: Roll back immediately on any acceptance failure**

If a protected-table count changes, totals do not match, the service fails, or key routes error, stop the service and restore the recorded release backup:

```bash
systemctl stop cam.service
cp "/root/cam-backups/${pam_release_stamp}/construction.sqlite3" /root/cam/instance/construction.sqlite3
tar -C /root -xzf "/root/cam-backups/${pam_release_stamp}/cam-code.tar.gz"
tar -C /root/cam -xzf "/root/cam-backups/${pam_release_stamp}/uploads.tar.gz"
systemctl start cam.service
```

Expected: the service returns to the pre-deploy project/voucher/contract state, and protected data remains available.

- [ ] **Step 11: Record final release evidence**

Append actual backup paths, deployed commit ID, full test count, dry-run totals, final SQL counts, service status, Nginx validation result, and any skipped authenticated browser check to the runbook’s release evidence section. Commit only the evidence update:

```bash
git add docs/runbooks/2026-07-26-project-ledger-production-import.md
git commit -m "docs: record project ledger release evidence"
```

## Final Verification Gate

Before claiming completion, invoke `superpowers:verification-before-completion` and rerun:

```bash
.venv/bin/pytest -q
.venv/bin/flask --app construction_maintenance ledger-import '/Users/rylinx/Downloads/各项目独立账套_汇总.zip'
git status --short
```

Then verify production protected-table counts, imported counts, totals, `systemctl is-active cam.service`, `nginx -t`, and the live login HTTP status from fresh output. Completion requires every approved acceptance value to match exactly.
