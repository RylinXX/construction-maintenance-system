# Construction Maintenance System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone web-based maintenance system for a construction engineering company, covering project vouchers, project ledgers, batch-entry queues, people records, company qualifications, dashboard metrics, and Excel exports.

**Architecture:** Create an independent Python Flask application with an app factory, SQLite persistence, repository/service modules, Jinja2 templates, and focused pytest coverage. Keep the system self-contained in this new project directory and do not depend on or modify the license-plate-recognition project.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, openpyxl, pytest, standard-library file uploads.

---

## Scope Check

This plan implements the first-version MVP from `docs/superpowers/specs/2026-05-29-construction-maintenance-system-design.md`.

Included:

- Main-company projects, vouchers, project ledgers, batch voucher queue, dashboard, and exports.
- People records with batch Excel import and reserved OCR review status.
- Company qualifications for the main company and other companies.
- Excel exports for project ledgers, monthly vouchers, basic people info, and qualification lists.

Excluded:

- Full accounting entries.
- Supplier/payee ledger tracking.
- Payroll and safety-education templates.
- Approval flows.
- Real OCR/AI extraction. The first version stores uploaded files and creates review tasks; OCR fields are reserved for a later integration.

## File Structure

- `.gitignore`: ignore local database, uploaded files, virtualenvs, caches, and exports.
- `pyproject.toml`: package metadata and runtime/test dependencies.
- `README.md`: local setup and run instructions.
- `construction_maintenance/__init__.py`: exports `create_app`.
- `construction_maintenance/app.py`: Flask application factory and blueprint registration.
- `construction_maintenance/config.py`: filesystem paths, database path, upload path.
- `construction_maintenance/db.py`: SQLite connection, schema creation, and seed data.
- `construction_maintenance/repositories.py`: database reads/writes for companies, projects, vouchers, people, qualifications, and batch items.
- `construction_maintenance/services/dashboard.py`: dashboard metric aggregation.
- `construction_maintenance/services/exports.py`: Excel export generation with openpyxl.
- `construction_maintenance/services/imports.py`: people Excel import parsing and batch-upload helpers.
- `construction_maintenance/web/routes.py`: page routes and form handlers.
- `construction_maintenance/web/forms.py`: form normalization and validation helpers.
- `construction_maintenance/templates/*.html`: Jinja2 pages.
- `construction_maintenance/static/app.css`: restrained business UI styling.
- `tests/conftest.py`: temporary app/database fixtures.
- `tests/test_db.py`: schema and seed tests.
- `tests/test_repositories.py`: data-layer tests.
- `tests/test_dashboard.py`: metric tests.
- `tests/test_exports.py`: Excel tests.
- `tests/test_routes.py`: web route smoke and form tests.

## Task 1: Scaffold Independent Flask Project

**Files:**

- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `construction_maintenance/__init__.py`
- Create: `construction_maintenance/app.py`
- Create: `construction_maintenance/config.py`
- Create: `construction_maintenance/web/__init__.py`
- Create: `construction_maintenance/web/routes.py`
- Create: `construction_maintenance/templates/base.html`
- Create: `construction_maintenance/templates/dashboard.html`
- Create: `construction_maintenance/static/app.css`
- Create: `tests/conftest.py`
- Test: `tests/test_routes.py`

- [ ] **Step 1: Write the failing route smoke test**

Create `tests/conftest.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from construction_maintenance import create_app


@pytest.fixture()
def app(tmp_path: Path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": tmp_path / "test.sqlite3",
            "UPLOAD_FOLDER": tmp_path / "uploads",
        }
    )
    return app


@pytest.fixture()
def client(app):
    return app.test_client()
```

Create `tests/test_routes.py`:

```python
from __future__ import annotations


def test_dashboard_route_renders(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "建筑工程维护系统".encode("utf-8") in response.data
    assert "项目支出".encode("utf-8") in response.data
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
pytest tests/test_routes.py::test_dashboard_route_renders -q
```

Expected: FAIL because the `construction_maintenance` package does not exist.

- [ ] **Step 3: Add project metadata and ignore rules**

Create `.gitignore`:

```gitignore
.venv/
__pycache__/
.pytest_cache/
*.pyc
*.sqlite3
instance/
uploads/
exports/
.env
```

Create `pyproject.toml`:

```toml
[project]
name = "construction-maintenance"
version = "0.1.0"
description = "A lightweight construction engineering maintenance system."
requires-python = ">=3.12"
dependencies = [
  "Flask>=3.0",
  "openpyxl>=3.1",
  "python-dateutil>=2.9",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Create `README.md`:

```markdown
# 建筑工程维护系统

一个独立的轻量 Web 系统，用于建筑工程公司的项目凭证台账、人员基础信息、企业资质和 Excel 导出。

## 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
flask --app construction_maintenance run --debug
```

打开 `http://127.0.0.1:5000`。
```

- [ ] **Step 4: Add the minimal app factory and routes**

Create `construction_maintenance/__init__.py`:

```python
from __future__ import annotations

from .app import create_app

__all__ = ["create_app"]
```

Create `construction_maintenance/config.py`:

```python
from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
DEFAULT_DATABASE = INSTANCE_DIR / "construction.sqlite3"
DEFAULT_UPLOAD_FOLDER = BASE_DIR / "uploads"
```

Create `construction_maintenance/app.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask

from .config import DEFAULT_DATABASE, DEFAULT_UPLOAD_FOLDER
from .web.routes import bp as web_bp


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DATABASE=DEFAULT_DATABASE,
        UPLOAD_FOLDER=DEFAULT_UPLOAD_FOLDER,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    app.register_blueprint(web_bp)
    return app
```

Create `construction_maintenance/web/__init__.py`:

```python
from __future__ import annotations
```

Create `construction_maintenance/web/routes.py`:

```python
from __future__ import annotations

from flask import Blueprint
from flask import render_template

bp = Blueprint("web", __name__)


@bp.get("/")
def dashboard():
    metrics = {
        "month_spending": "0.00",
        "total_spending": "0.00",
        "voucher_count": 0,
        "pending_count": 0,
        "expiring_qualifications": 0,
    }
    return render_template("dashboard.html", metrics=metrics)
```

Create `construction_maintenance/templates/base.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}建筑工程维护系统{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='app.css') }}">
  </head>
  <body>
    <aside class="sidebar">
      <div class="brand">建筑工程维护系统</div>
      <nav>
        <a href="{{ url_for('web.dashboard') }}">看板</a>
      </nav>
    </aside>
    <main class="main">
      {% block content %}{% endblock %}
    </main>
  </body>
</html>
```

Create `construction_maintenance/templates/dashboard.html`:

```html
{% extends "base.html" %}
{% block title %}看板 - 建筑工程维护系统{% endblock %}
{% block content %}
<header class="page-header">
  <h1>看板</h1>
</header>
<section class="metric-grid">
  <article class="metric"><span>本月项目支出</span><strong>¥{{ metrics.month_spending }}</strong></article>
  <article class="metric"><span>累计项目支出</span><strong>¥{{ metrics.total_spending }}</strong></article>
  <article class="metric"><span>本月凭证数</span><strong>{{ metrics.voucher_count }}</strong></article>
  <article class="metric"><span>待确认资料</span><strong>{{ metrics.pending_count }}</strong></article>
  <article class="metric"><span>临期资质</span><strong>{{ metrics.expiring_qualifications }}</strong></article>
</section>
{% endblock %}
```

Create `construction_maintenance/static/app.css`:

```css
:root {
  color-scheme: light;
  --bg: #f5f7f9;
  --panel: #ffffff;
  --text: #1f2933;
  --muted: #667085;
  --line: #d9e0e7;
  --accent: #0f766e;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  display: grid;
  grid-template-columns: 232px 1fr;
  background: var(--bg);
  color: var(--text);
  font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
}
.sidebar {
  background: #17212b;
  color: #fff;
  padding: 20px 16px;
}
.brand {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 24px;
}
.sidebar a {
  display: block;
  color: #dbe7ef;
  padding: 10px 12px;
  text-decoration: none;
  border-radius: 6px;
}
.sidebar a:hover { background: rgba(255,255,255,.1); }
.main { padding: 24px; }
.page-header { margin-bottom: 18px; }
.page-header h1 { margin: 0; font-size: 24px; }
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
.metric {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
}
.metric span { display: block; color: var(--muted); font-size: 13px; }
.metric strong { display: block; margin-top: 8px; font-size: 22px; }
```

- [ ] **Step 5: Run the smoke test**

Run:

```bash
pytest tests/test_routes.py::test_dashboard_route_renders -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .gitignore pyproject.toml README.md construction_maintenance tests
git commit -m "feat: scaffold construction maintenance app"
```

## Task 2: Add SQLite Schema and Seed Data

**Files:**

- Create: `construction_maintenance/db.py`
- Modify: `construction_maintenance/app.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write database tests**

Create `tests/test_db.py`:

```python
from __future__ import annotations

from construction_maintenance.db import get_db
from construction_maintenance.db import init_db


def test_init_db_creates_main_company(app):
    with app.app_context():
        init_db()
        company = get_db().execute(
            "select name, is_main from companies where is_main = 1"
        ).fetchone()

    assert company["name"] == "主公司"
    assert company["is_main"] == 1


def test_schema_contains_core_tables(app):
    with app.app_context():
        init_db()
        rows = get_db().execute(
            "select name from sqlite_master where type = 'table'"
        ).fetchall()

    table_names = {row["name"] for row in rows}
    assert {
        "companies",
        "projects",
        "vouchers",
        "people",
        "qualifications",
        "batch_items",
    }.issubset(table_names)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_db.py -q
```

Expected: FAIL because `construction_maintenance.db` does not exist.

- [ ] **Step 3: Implement database helpers and schema**

Create `construction_maintenance/db.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from flask import current_app
from flask import g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database = Path(current_app.config["DATABASE"])
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys = on")
        g.db = connection
    return g.db


def close_db(_: Any = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app) -> None:
    app.teardown_appcontext(close_db)


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        create table if not exists companies (
            id integer primary key autoincrement,
            name text not null unique,
            credit_code text not null default '',
            legal_person text not null default '',
            phone text not null default '',
            notes text not null default '',
            is_main integer not null default 0,
            created_at text not null default current_timestamp
        );

        create table if not exists projects (
            id integer primary key autoincrement,
            company_id integer not null references companies(id),
            name text not null,
            status text not null default '进行中',
            owner text not null default '',
            start_date text not null default '',
            end_date text not null default '',
            notes text not null default '',
            created_at text not null default current_timestamp
        );

        create table if not exists vouchers (
            id integer primary key autoincrement,
            project_id integer not null references projects(id),
            voucher_date text not null,
            voucher_type text not null,
            amount real not null check(amount > 0),
            notes text not null default '',
            attachment_path text not null default '',
            entry_user text not null default '',
            created_at text not null default current_timestamp
        );

        create table if not exists people (
            id integer primary key autoincrement,
            name text not null,
            id_number text not null unique,
            gender text not null default '',
            birth_date text not null default '',
            age integer,
            phone text not null default '',
            address text not null default '',
            job_type text not null default '',
            bank_card text not null default '',
            bank_name text not null default '',
            entry_date text not null default '',
            notes text not null default '',
            review_status text not null default '已确认',
            created_at text not null default current_timestamp
        );

        create table if not exists qualifications (
            id integer primary key autoincrement,
            company_id integer not null references companies(id),
            name text not null,
            certificate_no text not null,
            issue_date text not null default '',
            expiry_date text not null default '',
            is_long_term integer not null default 0,
            attachment_path text not null default '',
            notes text not null default '',
            created_at text not null default current_timestamp
        );

        create table if not exists batch_items (
            id integer primary key autoincrement,
            item_type text not null,
            source_filename text not null,
            stored_path text not null default '',
            status text not null default '待确认',
            recognized_json text not null default '{}',
            confidence real,
            created_at text not null default current_timestamp
        );
        """
    )
    db.execute(
        """
        insert into companies (name, is_main)
        select '主公司', 1
        where not exists (select 1 from companies where is_main = 1)
        """
    )
    db.commit()
```

Modify `construction_maintenance/app.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask

from . import db
from .config import DEFAULT_DATABASE, DEFAULT_UPLOAD_FOLDER
from .web.routes import bp as web_bp


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DATABASE=DEFAULT_DATABASE,
        UPLOAD_FOLDER=DEFAULT_UPLOAD_FOLDER,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.init_db()

    app.register_blueprint(web_bp)
    return app
```

- [ ] **Step 4: Run database tests**

Run:

```bash
pytest tests/test_db.py -q
```

Expected: PASS.

- [ ] **Step 5: Run the existing smoke test**

Run:

```bash
pytest tests/test_routes.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add construction_maintenance/app.py construction_maintenance/db.py tests/test_db.py
git commit -m "feat: add sqlite schema"
```

## Task 3: Add Repositories and Form Validation

**Files:**

- Create: `construction_maintenance/repositories.py`
- Create: `construction_maintenance/web/forms.py`
- Test: `tests/test_repositories.py`

- [ ] **Step 1: Write repository tests**

Create `tests/test_repositories.py`:

```python
from __future__ import annotations

import pytest

from construction_maintenance import repositories as repo


def test_create_project_and_voucher(app):
    with app.app_context():
        main_company = repo.get_main_company()
        project_id = repo.create_project(
            {
                "company_id": main_company["id"],
                "name": "土方工程",
                "status": "进行中",
                "owner": "张三",
                "start_date": "2026-05-29",
                "end_date": "",
                "notes": "",
            }
        )
        voucher_id = repo.create_voucher(
            {
                "project_id": project_id,
                "voucher_date": "2026-05-29",
                "voucher_type": "材料费用",
                "amount": 2300,
                "notes": "购买材料",
                "attachment_path": "",
                "entry_user": "财务",
            }
        )
        vouchers = repo.list_vouchers(project_id=project_id)

    assert voucher_id > 0
    assert vouchers[0]["project_name"] == "土方工程"
    assert vouchers[0]["amount"] == 2300


def test_voucher_amount_validation():
    with pytest.raises(ValueError, match="金额必须大于 0"):
        repo.normalize_amount("0")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_repositories.py -q
```

Expected: FAIL because repositories do not exist.

- [ ] **Step 3: Implement form helpers**

Create `construction_maintenance/web/forms.py`:

```python
from __future__ import annotations

from werkzeug.datastructures import ImmutableMultiDict


def text_value(form: ImmutableMultiDict[str, str], key: str) -> str:
    return (form.get(key) or "").strip()


def required_text(form: ImmutableMultiDict[str, str], key: str, label: str) -> str:
    value = text_value(form, key)
    if not value:
        raise ValueError(f"{label}不能为空")
    return value
```

- [ ] **Step 4: Implement repositories**

Create `construction_maintenance/repositories.py`:

```python
from __future__ import annotations

from typing import Any

from .db import get_db


def normalize_amount(value: Any) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("金额必须是数字") from exc
    if amount <= 0:
        raise ValueError("金额必须大于 0")
    return amount


def get_main_company():
    return get_db().execute("select * from companies where is_main = 1").fetchone()


def list_companies():
    return get_db().execute("select * from companies order by is_main desc, name").fetchall()


def create_company(data: dict[str, Any]) -> int:
    cursor = get_db().execute(
        """
        insert into companies (name, credit_code, legal_person, phone, notes, is_main)
        values (?, ?, ?, ?, ?, ?)
        """,
        (
            data["name"],
            data.get("credit_code", ""),
            data.get("legal_person", ""),
            data.get("phone", ""),
            data.get("notes", ""),
            int(data.get("is_main", 0)),
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)


def list_projects():
    return get_db().execute(
        """
        select projects.*, companies.name as company_name
        from projects
        join companies on companies.id = projects.company_id
        order by projects.created_at desc
        """
    ).fetchall()


def create_project(data: dict[str, Any]) -> int:
    cursor = get_db().execute(
        """
        insert into projects (company_id, name, status, owner, start_date, end_date, notes)
        values (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["company_id"],
            data["name"],
            data.get("status", "进行中"),
            data.get("owner", ""),
            data.get("start_date", ""),
            data.get("end_date", ""),
            data.get("notes", ""),
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)


def list_vouchers(project_id: int | None = None):
    params: list[Any] = []
    where = ""
    if project_id:
        where = "where vouchers.project_id = ?"
        params.append(project_id)
    return get_db().execute(
        f"""
        select vouchers.*, projects.name as project_name
        from vouchers
        join projects on projects.id = vouchers.project_id
        {where}
        order by vouchers.voucher_date desc, vouchers.created_at desc
        """,
        params,
    ).fetchall()


def create_voucher(data: dict[str, Any]) -> int:
    amount = normalize_amount(data["amount"])
    cursor = get_db().execute(
        """
        insert into vouchers
          (project_id, voucher_date, voucher_type, amount, notes, attachment_path, entry_user)
        values (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["project_id"],
            data["voucher_date"],
            data["voucher_type"],
            amount,
            data.get("notes", ""),
            data.get("attachment_path", ""),
            data.get("entry_user", ""),
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)
```

- [ ] **Step 5: Run repository tests**

Run:

```bash
pytest tests/test_repositories.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add construction_maintenance/repositories.py construction_maintenance/web/forms.py tests/test_repositories.py
git commit -m "feat: add repository layer"
```

## Task 4: Build Project and Voucher Pages

**Files:**

- Modify: `construction_maintenance/web/routes.py`
- Modify: `construction_maintenance/templates/base.html`
- Create: `construction_maintenance/templates/projects.html`
- Create: `construction_maintenance/templates/vouchers.html`
- Test: `tests/test_routes.py`

- [ ] **Step 1: Add route tests**

Append to `tests/test_routes.py`:

```python
def test_project_and_voucher_flow(client):
    project_response = client.post(
        "/projects",
        data={
            "name": "土方工程",
            "status": "进行中",
            "owner": "张三",
            "start_date": "2026-05-29",
            "end_date": "",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert project_response.status_code == 200
    assert "土方工程".encode("utf-8") in project_response.data

    voucher_response = client.post(
        "/vouchers",
        data={
            "project_id": "1",
            "voucher_date": "2026-05-29",
            "voucher_type": "材料费用",
            "amount": "2300",
            "notes": "购买材料",
            "entry_user": "财务",
        },
        follow_redirects=True,
    )
    assert voucher_response.status_code == 200
    assert "购买材料".encode("utf-8") in voucher_response.data
    assert "2,300.00".encode("utf-8") in voucher_response.data
```

- [ ] **Step 2: Run route tests and verify failure**

Run:

```bash
pytest tests/test_routes.py::test_project_and_voucher_flow -q
```

Expected: FAIL because `/projects` and `/vouchers` do not exist.

- [ ] **Step 3: Implement routes**

Replace `construction_maintenance/web/routes.py` with:

```python
from __future__ import annotations

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from construction_maintenance import repositories as repo
from construction_maintenance.web.forms import required_text
from construction_maintenance.web.forms import text_value

bp = Blueprint("web", __name__)


@bp.app_template_filter("money")
def money(value: float) -> str:
    return f"{float(value):,.2f}"


@bp.get("/")
def dashboard():
    vouchers = repo.list_vouchers()
    total = sum(float(row["amount"]) for row in vouchers)
    metrics = {
        "month_spending": f"{total:.2f}",
        "total_spending": f"{total:.2f}",
        "voucher_count": len(vouchers),
        "pending_count": 0,
        "expiring_qualifications": 0,
    }
    return render_template("dashboard.html", metrics=metrics)


@bp.route("/projects", methods=["GET", "POST"])
def projects():
    if request.method == "POST":
        main_company = repo.get_main_company()
        repo.create_project(
            {
                "company_id": main_company["id"],
                "name": required_text(request.form, "name", "项目名称"),
                "status": text_value(request.form, "status") or "进行中",
                "owner": text_value(request.form, "owner"),
                "start_date": text_value(request.form, "start_date"),
                "end_date": text_value(request.form, "end_date"),
                "notes": text_value(request.form, "notes"),
            }
        )
        return redirect(url_for("web.projects"))
    return render_template("projects.html", projects=repo.list_projects())


@bp.route("/vouchers", methods=["GET", "POST"])
def vouchers():
    if request.method == "POST":
        repo.create_voucher(
            {
                "project_id": int(required_text(request.form, "project_id", "项目")),
                "voucher_date": required_text(request.form, "voucher_date", "日期"),
                "voucher_type": required_text(request.form, "voucher_type", "凭证类型"),
                "amount": required_text(request.form, "amount", "金额"),
                "notes": text_value(request.form, "notes"),
                "attachment_path": "",
                "entry_user": text_value(request.form, "entry_user"),
            }
        )
        return redirect(url_for("web.vouchers"))
    return render_template(
        "vouchers.html",
        projects=repo.list_projects(),
        vouchers=repo.list_vouchers(),
        voucher_types=["员工报销", "转账凭证", "材料费用", "油费", "电费", "人工工资", "其它"],
    )
```

- [ ] **Step 4: Add navigation and templates**

Update `construction_maintenance/templates/base.html` navigation:

```html
<nav>
  <a href="{{ url_for('web.dashboard') }}">看板</a>
  <a href="{{ url_for('web.projects') }}">项目台账</a>
  <a href="{{ url_for('web.vouchers') }}">凭证录入</a>
</nav>
```

Create `construction_maintenance/templates/projects.html`:

```html
{% extends "base.html" %}
{% block title %}项目台账 - 建筑工程维护系统{% endblock %}
{% block content %}
<header class="page-header"><h1>项目台账</h1></header>
<section class="panel">
  <h2>新增项目</h2>
  <form method="post" class="form-grid">
    <label>项目名称<input name="name" required></label>
    <label>状态<input name="status" value="进行中"></label>
    <label>负责人<input name="owner"></label>
    <label>开始日期<input name="start_date" type="date"></label>
    <label>结束日期<input name="end_date" type="date"></label>
    <label class="full">备注<input name="notes"></label>
    <button type="submit">保存项目</button>
  </form>
</section>
<section class="panel">
  <h2>项目列表</h2>
  <table>
    <thead><tr><th>项目</th><th>状态</th><th>负责人</th><th>开始日期</th><th>备注</th></tr></thead>
    <tbody>
      {% for project in projects %}
      <tr><td>{{ project.name }}</td><td>{{ project.status }}</td><td>{{ project.owner }}</td><td>{{ project.start_date }}</td><td>{{ project.notes }}</td></tr>
      {% else %}
      <tr><td colspan="5">暂无项目</td></tr>
      {% endfor %}
    </tbody>
  </table>
</section>
{% endblock %}
```

Create `construction_maintenance/templates/vouchers.html`:

```html
{% extends "base.html" %}
{% block title %}凭证录入 - 建筑工程维护系统{% endblock %}
{% block content %}
<header class="page-header"><h1>凭证录入</h1></header>
<section class="panel">
  <h2>新增凭证</h2>
  <form method="post" class="form-grid">
    <label>日期<input name="voucher_date" type="date" required></label>
    <label>项目<select name="project_id" required>{% for project in projects %}<option value="{{ project.id }}">{{ project.name }}</option>{% endfor %}</select></label>
    <label>类型<select name="voucher_type" required>{% for item in voucher_types %}<option>{{ item }}</option>{% endfor %}</select></label>
    <label>金额<input name="amount" type="number" min="0.01" step="0.01" required></label>
    <label>录入人<input name="entry_user"></label>
    <label class="full">备注<input name="notes"></label>
    <button type="submit">保存并进入项目台账</button>
  </form>
</section>
<section class="panel">
  <h2>凭证明细</h2>
  <table>
    <thead><tr><th>日期</th><th>项目</th><th>类型</th><th>金额</th><th>备注</th><th>录入人</th></tr></thead>
    <tbody>
      {% for voucher in vouchers %}
      <tr><td>{{ voucher.voucher_date }}</td><td>{{ voucher.project_name }}</td><td>{{ voucher.voucher_type }}</td><td>{{ voucher.amount|money }}</td><td>{{ voucher.notes }}</td><td>{{ voucher.entry_user }}</td></tr>
      {% else %}
      <tr><td colspan="6">暂无凭证</td></tr>
      {% endfor %}
    </tbody>
  </table>
</section>
{% endblock %}
```

- [ ] **Step 5: Extend CSS for forms and tables**

Append to `construction_maintenance/static/app.css`:

```css
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  margin-bottom: 16px;
}
.panel h2 { margin: 0 0 14px; font-size: 18px; }
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.form-grid label { display: grid; gap: 6px; color: var(--muted); font-size: 13px; }
.form-grid input, .form-grid select {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 9px 10px;
  font: inherit;
}
.form-grid .full { grid-column: 1 / -1; }
button {
  border: 0;
  border-radius: 6px;
  padding: 10px 14px;
  background: var(--accent);
  color: #fff;
  font: inherit;
  cursor: pointer;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
th, td {
  border-bottom: 1px solid var(--line);
  padding: 10px 8px;
  text-align: left;
}
th { color: var(--muted); font-weight: 600; }
```

- [ ] **Step 6: Run route tests**

Run:

```bash
pytest tests/test_routes.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add construction_maintenance tests/test_routes.py
git commit -m "feat: add project and voucher pages"
```

## Task 5: Add People Records and Basic People Export

**Files:**

- Modify: `construction_maintenance/repositories.py`
- Modify: `construction_maintenance/web/routes.py`
- Modify: `construction_maintenance/templates/base.html`
- Create: `construction_maintenance/templates/people.html`
- Create: `construction_maintenance/services/exports.py`
- Test: `tests/test_exports.py`
- Test: `tests/test_routes.py`

- [ ] **Step 1: Write export test**

Create `tests/test_exports.py`:

```python
from __future__ import annotations

from openpyxl import load_workbook

from construction_maintenance import repositories as repo
from construction_maintenance.services.exports import build_people_workbook


def test_build_people_workbook(app, tmp_path):
    with app.app_context():
        repo.create_person(
            {
                "name": "王小明",
                "id_number": "410000199001011234",
                "gender": "男",
                "birth_date": "1990-01-01",
                "age": 36,
                "phone": "13800000000",
                "address": "河南省郑州市",
                "job_type": "普工",
                "bank_card": "6222000000000000",
                "bank_name": "建设银行",
                "entry_date": "2026-05-29",
                "notes": "",
            }
        )
        output = tmp_path / "people.xlsx"
        build_people_workbook(output)

    workbook = load_workbook(output)
    sheet = workbook.active
    assert sheet["A1"].value == "姓名"
    assert sheet["A2"].value == "王小明"
    assert sheet["B2"].value == "410000199001011234"
```

- [ ] **Step 2: Run export test and verify failure**

Run:

```bash
pytest tests/test_exports.py::test_build_people_workbook -q
```

Expected: FAIL because people repository and exports service do not exist.

- [ ] **Step 3: Add people repository functions**

Append to `construction_maintenance/repositories.py`:

```python
def list_people():
    return get_db().execute("select * from people order by created_at desc").fetchall()


def create_person(data: dict[str, Any]) -> int:
    cursor = get_db().execute(
        """
        insert into people
          (name, id_number, gender, birth_date, age, phone, address, job_type,
           bank_card, bank_name, entry_date, notes, review_status)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["name"],
            data["id_number"],
            data.get("gender", ""),
            data.get("birth_date", ""),
            data.get("age"),
            data.get("phone", ""),
            data.get("address", ""),
            data.get("job_type", ""),
            data.get("bank_card", ""),
            data.get("bank_name", ""),
            data.get("entry_date", ""),
            data.get("notes", ""),
            data.get("review_status", "已确认"),
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)
```

- [ ] **Step 4: Implement people export service**

Create `construction_maintenance/services/exports.py`:

```python
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
```

- [ ] **Step 5: Run export test**

Run:

```bash
pytest tests/test_exports.py::test_build_people_workbook -q
```

Expected: PASS.

- [ ] **Step 6: Add people page routes and template**

Append to `construction_maintenance/web/routes.py`:

```python
@bp.route("/people", methods=["GET", "POST"])
def people():
    if request.method == "POST":
        repo.create_person(
            {
                "name": required_text(request.form, "name", "姓名"),
                "id_number": required_text(request.form, "id_number", "身份证号"),
                "gender": text_value(request.form, "gender"),
                "birth_date": text_value(request.form, "birth_date"),
                "age": int(text_value(request.form, "age") or 0) or None,
                "phone": text_value(request.form, "phone"),
                "address": text_value(request.form, "address"),
                "job_type": text_value(request.form, "job_type"),
                "bank_card": text_value(request.form, "bank_card"),
                "bank_name": text_value(request.form, "bank_name"),
                "entry_date": text_value(request.form, "entry_date"),
                "notes": text_value(request.form, "notes"),
            }
        )
        return redirect(url_for("web.people"))
    return render_template("people.html", people=repo.list_people())
```

Add this link to `base.html` navigation:

```html
<a href="{{ url_for('web.people') }}">人员花名册</a>
```

Create `construction_maintenance/templates/people.html`:

```html
{% extends "base.html" %}
{% block title %}人员花名册 - 建筑工程维护系统{% endblock %}
{% block content %}
<header class="page-header"><h1>人员花名册</h1></header>
<section class="panel">
  <h2>新增人员</h2>
  <form method="post" class="form-grid">
    <label>姓名<input name="name" required></label>
    <label>身份证号<input name="id_number" required></label>
    <label>性别<input name="gender"></label>
    <label>出生日期<input name="birth_date" type="date"></label>
    <label>年龄<input name="age" type="number" min="0"></label>
    <label>电话<input name="phone"></label>
    <label>岗位/工种<input name="job_type"></label>
    <label>银行卡号<input name="bank_card"></label>
    <label>开户行<input name="bank_name"></label>
    <label>入职/进场日期<input name="entry_date" type="date"></label>
    <label class="full">住址<input name="address"></label>
    <label class="full">备注<input name="notes"></label>
    <button type="submit">保存人员</button>
  </form>
</section>
<section class="panel">
  <h2>基础人员信息</h2>
  <table>
    <thead><tr><th>姓名</th><th>身份证号</th><th>电话</th><th>岗位/工种</th><th>银行卡</th><th>状态</th></tr></thead>
    <tbody>
      {% for person in people %}
      <tr><td>{{ person.name }}</td><td>{{ person.id_number }}</td><td>{{ person.phone }}</td><td>{{ person.job_type }}</td><td>{{ person.bank_card }}</td><td>{{ person.review_status }}</td></tr>
      {% else %}
      <tr><td colspan="6">暂无人员</td></tr>
      {% endfor %}
    </tbody>
  </table>
</section>
{% endblock %}
```

- [ ] **Step 7: Add route smoke test for people**

Append to `tests/test_routes.py`:

```python
def test_people_page_creates_person(client):
    response = client.post(
        "/people",
        data={
            "name": "王小明",
            "id_number": "410000199001011234",
            "phone": "13800000000",
            "job_type": "普工",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "王小明".encode("utf-8") in response.data
```

- [ ] **Step 8: Run tests**

Run:

```bash
pytest tests/test_exports.py tests/test_routes.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add construction_maintenance tests
git commit -m "feat: add people records and export"
```

## Task 6: Add Companies and Qualifications

**Files:**

- Modify: `construction_maintenance/repositories.py`
- Modify: `construction_maintenance/web/routes.py`
- Modify: `construction_maintenance/templates/base.html`
- Create: `construction_maintenance/templates/qualifications.html`
- Modify: `construction_maintenance/services/exports.py`
- Test: `tests/test_exports.py`
- Test: `tests/test_routes.py`

- [ ] **Step 1: Add qualification export test**

Append to `tests/test_exports.py`:

```python
from construction_maintenance.services.exports import build_qualification_workbook


def test_build_qualification_workbook(app, tmp_path):
    with app.app_context():
        company = repo.get_main_company()
        repo.create_qualification(
            {
                "company_id": company["id"],
                "name": "建筑业企业资质",
                "certificate_no": "D300000",
                "issue_date": "2026-01-01",
                "expiry_date": "2029-01-01",
                "is_long_term": 0,
                "attachment_path": "",
                "notes": "",
            }
        )
        output = tmp_path / "qualifications.xlsx"
        build_qualification_workbook(output)

    workbook = load_workbook(output)
    sheet = workbook.active
    assert sheet["A1"].value == "公司"
    assert sheet["B2"].value == "建筑业企业资质"
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
pytest tests/test_exports.py::test_build_qualification_workbook -q
```

Expected: FAIL because qualification repository/export functions do not exist.

- [ ] **Step 3: Add qualification repository functions**

Append to `construction_maintenance/repositories.py`:

```python
def list_qualifications():
    return get_db().execute(
        """
        select qualifications.*, companies.name as company_name
        from qualifications
        join companies on companies.id = qualifications.company_id
        order by companies.is_main desc, companies.name, qualifications.expiry_date
        """
    ).fetchall()


def create_qualification(data: dict[str, Any]) -> int:
    cursor = get_db().execute(
        """
        insert into qualifications
          (company_id, name, certificate_no, issue_date, expiry_date,
           is_long_term, attachment_path, notes)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["company_id"],
            data["name"],
            data["certificate_no"],
            data.get("issue_date", ""),
            data.get("expiry_date", ""),
            int(data.get("is_long_term", 0)),
            data.get("attachment_path", ""),
            data.get("notes", ""),
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)
```

- [ ] **Step 4: Add qualification export**

Append to `construction_maintenance/services/exports.py`:

```python
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
```

- [ ] **Step 5: Run export tests**

Run:

```bash
pytest tests/test_exports.py -q
```

Expected: PASS.

- [ ] **Step 6: Add qualification routes and page**

Append to `construction_maintenance/web/routes.py`:

```python
@bp.route("/qualifications", methods=["GET", "POST"])
def qualifications():
    if request.method == "POST":
        if text_value(request.form, "company_name"):
            company_id = repo.create_company(
                {
                    "name": required_text(request.form, "company_name", "公司名称"),
                    "credit_code": text_value(request.form, "credit_code"),
                    "legal_person": text_value(request.form, "legal_person"),
                    "phone": text_value(request.form, "phone"),
                    "notes": text_value(request.form, "company_notes"),
                    "is_main": 0,
                }
            )
        else:
            company_id = int(required_text(request.form, "company_id", "公司"))
        repo.create_qualification(
            {
                "company_id": company_id,
                "name": required_text(request.form, "name", "资质名称"),
                "certificate_no": required_text(request.form, "certificate_no", "证书编号"),
                "issue_date": text_value(request.form, "issue_date"),
                "expiry_date": text_value(request.form, "expiry_date"),
                "is_long_term": 1 if request.form.get("is_long_term") else 0,
                "attachment_path": "",
                "notes": text_value(request.form, "notes"),
            }
        )
        return redirect(url_for("web.qualifications"))
    return render_template(
        "qualifications.html",
        companies=repo.list_companies(),
        qualifications=repo.list_qualifications(),
    )
```

Add this link to `base.html` navigation:

```html
<a href="{{ url_for('web.qualifications') }}">企业资质</a>
```

Create `construction_maintenance/templates/qualifications.html`:

```html
{% extends "base.html" %}
{% block title %}企业资质 - 建筑工程维护系统{% endblock %}
{% block content %}
<header class="page-header"><h1>企业资质</h1></header>
<section class="panel">
  <h2>新增资质</h2>
  <form method="post" class="form-grid">
    <label>已有公司<select name="company_id">{% for company in companies %}<option value="{{ company.id }}">{{ company.name }}</option>{% endfor %}</select></label>
    <label>或新增公司<input name="company_name" placeholder="不填则使用已有公司"></label>
    <label>统一社会信用代码<input name="credit_code"></label>
    <label>法定代表人<input name="legal_person"></label>
    <label>公司电话<input name="phone"></label>
    <label>资质名称<input name="name" required></label>
    <label>证书编号<input name="certificate_no" required></label>
    <label>发证日期<input name="issue_date" type="date"></label>
    <label>到期日期<input name="expiry_date" type="date"></label>
    <label>长期有效<input name="is_long_term" type="checkbox" value="1"></label>
    <label class="full">备注<input name="notes"></label>
    <button type="submit">保存资质</button>
  </form>
</section>
<section class="panel">
  <h2>资质清单</h2>
  <table>
    <thead><tr><th>公司</th><th>资质</th><th>证书编号</th><th>发证日期</th><th>到期日期</th><th>长期</th></tr></thead>
    <tbody>
      {% for item in qualifications %}
      <tr><td>{{ item.company_name }}</td><td>{{ item.name }}</td><td>{{ item.certificate_no }}</td><td>{{ item.issue_date }}</td><td>{{ item.expiry_date }}</td><td>{{ "是" if item.is_long_term else "否" }}</td></tr>
      {% else %}
      <tr><td colspan="6">暂无资质</td></tr>
      {% endfor %}
    </tbody>
  </table>
</section>
{% endblock %}
```

- [ ] **Step 7: Add route test**

Append to `tests/test_routes.py`:

```python
def test_qualification_page_creates_qualification(client):
    response = client.post(
        "/qualifications",
        data={
            "company_id": "1",
            "name": "建筑业企业资质",
            "certificate_no": "D300000",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "建筑业企业资质".encode("utf-8") in response.data
```

- [ ] **Step 8: Run tests**

Run:

```bash
pytest tests/test_exports.py tests/test_routes.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add construction_maintenance tests
git commit -m "feat: add qualification management"
```

## Task 7: Add Batch Upload Queue

**Files:**

- Modify: `construction_maintenance/repositories.py`
- Create: `construction_maintenance/services/imports.py`
- Modify: `construction_maintenance/web/routes.py`
- Modify: `construction_maintenance/templates/base.html`
- Create: `construction_maintenance/templates/batch.html`
- Test: `tests/test_repositories.py`
- Test: `tests/test_routes.py`

- [ ] **Step 1: Add batch repository test**

Append to `tests/test_repositories.py`:

```python
def test_create_batch_item(app):
    with app.app_context():
        item_id = repo.create_batch_item(
            {
                "item_type": "voucher",
                "source_filename": "pay.png",
                "stored_path": "uploads/pay.png",
                "status": "待确认",
                "recognized_json": "{}",
                "confidence": None,
            }
        )
        items = repo.list_batch_items("voucher")

    assert item_id > 0
    assert items[0]["source_filename"] == "pay.png"
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
pytest tests/test_repositories.py::test_create_batch_item -q
```

Expected: FAIL because batch repository functions do not exist.

- [ ] **Step 3: Add batch repository functions**

Append to `construction_maintenance/repositories.py`:

```python
def create_batch_item(data: dict[str, Any]) -> int:
    cursor = get_db().execute(
        """
        insert into batch_items
          (item_type, source_filename, stored_path, status, recognized_json, confidence)
        values (?, ?, ?, ?, ?, ?)
        """,
        (
            data["item_type"],
            data["source_filename"],
            data.get("stored_path", ""),
            data.get("status", "待确认"),
            data.get("recognized_json", "{}"),
            data.get("confidence"),
        ),
    )
    get_db().commit()
    return int(cursor.lastrowid)


def list_batch_items(item_type: str | None = None):
    if item_type:
        return get_db().execute(
            "select * from batch_items where item_type = ? order by created_at desc",
            (item_type,),
        ).fetchall()
    return get_db().execute("select * from batch_items order by created_at desc").fetchall()
```

- [ ] **Step 4: Add upload helper**

Create `construction_maintenance/services/imports.py`:

```python
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


def save_upload(upload_folder: Path, file: FileStorage) -> Path:
    original = secure_filename(file.filename or "upload")
    filename = f"{uuid4().hex}_{original}"
    upload_folder.mkdir(parents=True, exist_ok=True)
    target = upload_folder / filename
    file.save(target)
    return target
```

- [ ] **Step 5: Add batch route and page**

Append to `construction_maintenance/web/routes.py`:

```python
from pathlib import Path

from flask import current_app

from construction_maintenance.services.imports import save_upload


@bp.route("/batch", methods=["GET", "POST"])
def batch():
    if request.method == "POST":
        item_type = text_value(request.form, "item_type") or "voucher"
        upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
        for file in request.files.getlist("files"):
            if not file.filename:
                continue
            stored = save_upload(upload_folder, file)
            repo.create_batch_item(
                {
                    "item_type": item_type,
                    "source_filename": file.filename,
                    "stored_path": str(stored),
                    "status": "待确认",
                    "recognized_json": "{}",
                    "confidence": None,
                }
            )
        return redirect(url_for("web.batch"))
    return render_template("batch.html", items=repo.list_batch_items())
```

Add this link to `base.html` navigation:

```html
<a href="{{ url_for('web.batch') }}">批量录入</a>
```

Create `construction_maintenance/templates/batch.html`:

```html
{% extends "base.html" %}
{% block title %}批量录入 - 建筑工程维护系统{% endblock %}
{% block content %}
<header class="page-header"><h1>批量录入</h1></header>
<section class="panel">
  <h2>批量上传</h2>
  <form method="post" enctype="multipart/form-data" class="form-grid">
    <label>类型<select name="item_type"><option value="voucher">凭证</option><option value="person">人员身份证</option></select></label>
    <label class="full">文件<input name="files" type="file" multiple required></label>
    <button type="submit">上传并进入待确认</button>
  </form>
</section>
<section class="panel">
  <h2>待确认列表</h2>
  <table>
    <thead><tr><th>类型</th><th>原文件名</th><th>状态</th><th>识别结果</th><th>创建时间</th></tr></thead>
    <tbody>
      {% for item in items %}
      <tr><td>{{ item.item_type }}</td><td>{{ item.source_filename }}</td><td>{{ item.status }}</td><td>{{ item.recognized_json }}</td><td>{{ item.created_at }}</td></tr>
      {% else %}
      <tr><td colspan="5">暂无批量任务</td></tr>
      {% endfor %}
    </tbody>
  </table>
</section>
{% endblock %}
```

- [ ] **Step 6: Add batch route test**

Append to `tests/test_routes.py`:

```python
from io import BytesIO


def test_batch_upload_creates_pending_item(client):
    response = client.post(
        "/batch",
        data={
            "item_type": "voucher",
            "files": (BytesIO(b"fake image"), "pay.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "pay.png".encode("utf-8") in response.data
    assert "待确认".encode("utf-8") in response.data
```

- [ ] **Step 7: Run tests**

Run:

```bash
pytest tests/test_repositories.py tests/test_routes.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add construction_maintenance tests
git commit -m "feat: add batch upload queue"
```

## Task 8: Add Dashboard Metrics and Export Center

**Files:**

- Create: `construction_maintenance/services/dashboard.py`
- Modify: `construction_maintenance/services/exports.py`
- Modify: `construction_maintenance/web/routes.py`
- Modify: `construction_maintenance/templates/base.html`
- Modify: `construction_maintenance/templates/dashboard.html`
- Create: `construction_maintenance/templates/exports.html`
- Test: `tests/test_dashboard.py`
- Test: `tests/test_exports.py`
- Test: `tests/test_routes.py`

- [ ] **Step 1: Write dashboard service test**

Create `tests/test_dashboard.py`:

```python
from __future__ import annotations

from construction_maintenance import repositories as repo
from construction_maintenance.services.dashboard import build_dashboard


def test_dashboard_counts_vouchers_and_pending_items(app):
    with app.app_context():
        company = repo.get_main_company()
        project_id = repo.create_project({"company_id": company["id"], "name": "土方工程"})
        repo.create_voucher(
            {
                "project_id": project_id,
                "voucher_date": "2026-05-29",
                "voucher_type": "油费",
                "amount": 500,
            }
        )
        repo.create_batch_item({"item_type": "voucher", "source_filename": "pay.png"})
        dashboard = build_dashboard()

    assert dashboard["total_spending"] == 500
    assert dashboard["voucher_count"] == 1
    assert dashboard["pending_count"] == 1
```

- [ ] **Step 2: Run dashboard test and verify failure**

Run:

```bash
pytest tests/test_dashboard.py -q
```

Expected: FAIL because dashboard service does not exist.

- [ ] **Step 3: Implement dashboard service**

Create `construction_maintenance/services/dashboard.py`:

```python
from __future__ import annotations

from collections import defaultdict
from datetime import date

from construction_maintenance import repositories as repo


def build_dashboard() -> dict:
    current_month = date.today().strftime("%Y-%m")
    vouchers = repo.list_vouchers()
    batch_items = repo.list_batch_items()
    total_spending = sum(float(row["amount"]) for row in vouchers)
    month_spending = sum(
        float(row["amount"]) for row in vouchers if str(row["voucher_date"]).startswith(current_month)
    )
    by_project: dict[str, float] = defaultdict(float)
    by_type: dict[str, float] = defaultdict(float)
    for row in vouchers:
        by_project[row["project_name"]] += float(row["amount"])
        by_type[row["voucher_type"]] += float(row["amount"])
    return {
        "month_spending": month_spending,
        "total_spending": total_spending,
        "voucher_count": len(vouchers),
        "pending_count": sum(1 for row in batch_items if row["status"] == "待确认"),
        "expiring_qualifications": 0,
        "by_project": sorted(by_project.items(), key=lambda item: item[1], reverse=True),
        "by_type": sorted(by_type.items(), key=lambda item: item[1], reverse=True),
    }
```

- [ ] **Step 4: Add project and voucher export functions**

Append to `construction_maintenance/services/exports.py`:

```python
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
```

- [ ] **Step 5: Route dashboard through service and add export center**

Modify the dashboard route in `construction_maintenance/web/routes.py`:

```python
from flask import send_file
from construction_maintenance.services.dashboard import build_dashboard
from construction_maintenance.services.exports import build_people_workbook
from construction_maintenance.services.exports import build_project_ledger_workbook
from construction_maintenance.services.exports import build_qualification_workbook
```

Replace the `dashboard` route body:

```python
@bp.get("/")
def dashboard():
    return render_template("dashboard.html", metrics=build_dashboard())
```

Append export routes:

```python
@bp.get("/exports")
def exports():
    return render_template("exports.html")


@bp.get("/exports/<export_type>")
def download_export(export_type: str):
    from flask import current_app

    export_dir = Path(current_app.root_path).parent / "exports"
    builders = {
        "project-ledger": ("项目台账.xlsx", build_project_ledger_workbook),
        "people": ("基础人员信息表.xlsx", build_people_workbook),
        "qualifications": ("企业资质清单.xlsx", build_qualification_workbook),
    }
    if export_type not in builders:
        return "Unknown export type", 404
    filename, builder = builders[export_type]
    path = builder(export_dir / filename)
    return send_file(path, as_attachment=True, download_name=filename)
```

Add this link to `base.html` navigation:

```html
<a href="{{ url_for('web.exports') }}">导出中心</a>
```

Update `dashboard.html` metric values:

```html
<article class="metric"><span>本月项目支出</span><strong>¥{{ metrics.month_spending|money }}</strong></article>
<article class="metric"><span>累计项目支出</span><strong>¥{{ metrics.total_spending|money }}</strong></article>
```

Create `construction_maintenance/templates/exports.html`:

```html
{% extends "base.html" %}
{% block title %}导出中心 - 建筑工程维护系统{% endblock %}
{% block content %}
<header class="page-header"><h1>导出中心</h1></header>
<section class="panel action-list">
  <a class="button-link" href="{{ url_for('web.download_export', export_type='project-ledger') }}">导出项目台账 Excel</a>
  <a class="button-link" href="{{ url_for('web.download_export', export_type='people') }}">导出基础人员信息表 Excel</a>
  <a class="button-link" href="{{ url_for('web.download_export', export_type='qualifications') }}">导出企业资质清单 Excel</a>
</section>
{% endblock %}
```

Append to CSS:

```css
.action-list { display: flex; flex-wrap: wrap; gap: 10px; }
.button-link {
  display: inline-flex;
  align-items: center;
  min-height: 40px;
  padding: 9px 14px;
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
  text-decoration: none;
}
```

- [ ] **Step 6: Add export route smoke test**

Append to `tests/test_routes.py`:

```python
def test_export_center_downloads_people_workbook(client):
    response = client.get("/exports/people")

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
```

- [ ] **Step 7: Run tests**

Run:

```bash
pytest tests/test_dashboard.py tests/test_exports.py tests/test_routes.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add construction_maintenance tests
git commit -m "feat: add dashboard metrics and exports"
```

## Task 9: Manual Web Verification and README Update

**Files:**

- Modify: `README.md`
- Test: browser/manual verification

- [ ] **Step 1: Update README with feature coverage**

Append to `README.md`:

```markdown
## 第一版功能

- 看板：项目支出、凭证数量、待确认资料和资质提醒入口。
- 项目台账：主公司项目维护和凭证明细。
- 凭证录入：日期、项目、类型、金额、备注和录入人。
- 批量录入：批量上传凭证或身份证文件，进入待确认队列。
- 人员花名册：基础人员信息维护。
- 企业资质：多公司资质证书管理。
- 导出中心：项目台账、基础人员信息表、企业资质清单。

## 测试

```powershell
pytest
```
```

- [ ] **Step 2: Run all automated tests**

Run:

```bash
pytest -q
```

Expected: all tests PASS.

- [ ] **Step 3: Start the local server**

Run:

```bash
flask --app construction_maintenance run --debug
```

Expected: Flask prints a local URL, usually `http://127.0.0.1:5000`.

- [ ] **Step 4: Verify pages manually**

Open the local URL and verify:

- The dashboard is visible and not blank.
- Create a project named `土方工程`.
- Create a voucher for `土方工程` with amount `2300`.
- Create a person named `王小明`.
- Create a qualification named `建筑业企业资质`.
- Upload a file through batch entry and confirm it appears as `待确认`.
- Download the people export and confirm it opens as an Excel file.

- [ ] **Step 5: Commit documentation update**

```bash
git add README.md
git commit -m "docs: add run and verification notes"
```

## Self-Review Checklist

- Spec coverage: project vouchers, batch entry, people records, qualifications, dashboard, and Excel exports are mapped to tasks.
- Boundary check: this project lives under `C:/Users/scodi.KYLINX/Documents/建筑工程维护系统` and does not modify the license-plate-recognition project.
- Personnel export check: only the basic people information export is planned; payroll and safety-education templates are not included.
- AI/OCR check: batch queue and review fields are implemented; real AI/OCR extraction is explicitly outside the first implementation.
- Validation check: required fields and positive voucher amount are covered by repository or form helpers.
