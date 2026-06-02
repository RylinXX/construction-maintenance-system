# AI Interview Style Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the Flask/Jinja construction maintenance system to match the warm enterprise workbench visual language from `RylinXX/ai-interview-boss-mail` while preserving existing behavior.

**Architecture:** Keep the server-rendered Flask/Jinja architecture. Implement the redesign by updating shared CSS primitives, the base application shell, and the dashboard hero markup without changing routes, services, repositories, or database state.

**Tech Stack:** Python 3.11+, Flask, Jinja2, SQLite, CSS, Chart.js, pytest.

---

## File Structure

- Modify `construction_maintenance/static/app.css`: replace the current blue/slate theme tokens and shared component styles with the warm workbench theme, including dark mode and responsive behavior.
- Modify `construction_maintenance/templates/base.html`: update shell markup to support fixed light sidebar, brand lockup, page title group, sticky header, theme toggle, and sidebar status.
- Modify `construction_maintenance/templates/dashboard.html`: update dashboard hero and KPI card markup to expose the new workbench layout while reusing existing `metrics`.
- Add `tests/test_ui_theme.py`: test the expected workbench tokens and shell markers before implementation, then keep it as a regression check.

The current directory is not a Git repository, so commit steps are intentionally omitted.

---

### Task 1: Add Regression Test For Workbench Theme Markers

**Files:**
- Add: `tests/test_ui_theme.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_reference_workbench_theme_tokens_are_present():
    css = read_text("construction_maintenance/static/app.css")

    assert "--surface-color: #FFFDF8;" in css
    assert "--secondary-color: #B88A3B;" in css
    assert "--background-color: #F7F4EE;" in css
    assert ".dashboard-hero" in css
    assert ".sidebar-status" in css


def test_base_shell_exposes_workbench_regions():
    base_html = read_text("construction_maintenance/templates/base.html")

    assert "brand-lockup" in base_html
    assert "page-title-group" in base_html
    assert "sidebar-status" in base_html


def test_dashboard_uses_workbench_hero():
    dashboard_html = read_text("construction_maintenance/templates/dashboard.html")

    assert "dashboard-hero" in dashboard_html
    assert "dashboard-hero-panel" in dashboard_html
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_ui_theme.py -q
```

Expected: fails because the current CSS and templates still use the older blue/slate shell and `welcome-banner`.

---

### Task 2: Update Base Shell Markup

**Files:**
- Modify: `construction_maintenance/templates/base.html`

- [ ] **Step 1: Replace the sidebar brand with workbench lockup**

Use this structure:

```html
<div class="brand-lockup">
  <div class="brand-mark" aria-hidden="true">CM</div>
  <div class="brand-copy">
    <div class="brand-name">CAM <span>维护系统</span></div>
    <div class="brand-subtitle">Construction Ops</div>
  </div>
</div>
```

- [ ] **Step 2: Keep existing route links and replace sidebar footer with status block**

Use:

```html
<div class="sidebar-status">
  <span class="status-dot" aria-hidden="true"></span>
  <div>
    <strong>维护数据在线</strong>
    <span>项目 / 人员 / 资质同步管理</span>
  </div>
</div>
```

- [ ] **Step 3: Replace breadcrumb-only header with title group**

Use:

```html
<div class="page-title-group">
  <div>
    <h2>{% block page_title %}{% block breadcrumb %}看板{% endblock %}{% endblock %}</h2>
    <span>{% block page_subtitle %}建筑工程维护数据工作台{% endblock %}</span>
  </div>
</div>
```

- [ ] **Step 4: Keep theme toggle behavior unchanged**

Only update the button and user wrapper classes; keep `toggleTheme()` and `localStorage` behavior intact.

---

### Task 3: Replace Global CSS With Warm Workbench Theme

**Files:**
- Modify: `construction_maintenance/static/app.css`

- [ ] **Step 1: Replace design tokens**

Define warm light variables and dark slate variables:

```css
:root {
  --primary-color: #142136;
  --primary-hover: #1d2c46;
  --secondary-color: #b88a3b;
  --accent-color: #57708f;
  --background-color: #f7f4ee;
  --surface-color: #fffdf8;
  --surface-elevated: #ffffff;
  --surface-muted: #fbf7ef;
  --surface-subtle: #f3ece0;
  --surface-inset: #efe6d8;
  --header-bg: rgba(255, 253, 248, 0.92);
  --menu-selected-bg: rgba(184, 138, 59, 0.14);
  --hover-bg: rgba(184, 138, 59, 0.08);
  --chart-grid: #e5ddcf;
  --text-primary: #172033;
  --text-secondary: #667085;
  --text-tertiary: #9b8d79;
  --border-color: #e5ddcf;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 8px;
}
```

- [ ] **Step 2: Map existing legacy variables**

Keep compatibility with current templates by mapping `--bg`, `--panel`, `--text`, `--muted`, `--line`, `--line-light`, `--primary`, and `--accent` to the new values.

- [ ] **Step 3: Restyle shell, cards, tables, forms, buttons, badges, modals, and dashboard**

Use the reference layout principles: fixed sidebar, sticky header, compact cards, warm hover states, gold primary actions, and 8px radius.

- [ ] **Step 4: Add responsive rules**

At widths below 980px, collapse sidebar width and hide brand copy/status. At widths below 760px, remove fixed sidebar and use single-column content.

---

### Task 4: Update Dashboard Hero And KPI Markup

**Files:**
- Modify: `construction_maintenance/templates/dashboard.html`

- [ ] **Step 1: Replace `welcome-banner` with `dashboard-hero`**

Reuse existing metrics and introduce a compact snapshot panel:

```html
<section class="dashboard-hero animate-slide-up">
  <div class="dashboard-hero-copy">
    <span class="eyebrow">Construction Maintenance OS</span>
    <h1>建筑工程维护数据工作台</h1>
    <p>集中跟踪项目支出、凭证录入、人员花名册与企业资质状态。</p>
  </div>
  <div class="dashboard-hero-panel">
    <div>
      <span>本月支出</span>
      <strong>¥{{ metrics.month_spending|money }}</strong>
    </div>
    <div>
      <span>待确认资料</span>
      <strong>{{ metrics.pending_count }}</strong>
    </div>
    <div>
      <span>临期资质</span>
      <strong>{{ metrics.expiring_qualifications }}</strong>
    </div>
  </div>
</section>
```

- [ ] **Step 2: Add metric baseline text**

Each metric card should include a short muted `.metric-baseline` line so the cards match the reference KPI density.

---

### Task 5: Verify And Iterate

**Files:**
- Test: `tests/test_ui_theme.py`
- Test: existing `tests/*.py`

- [ ] **Step 1: Run targeted theme test**

Run:

```powershell
python -m pytest tests/test_ui_theme.py -q
```

Expected: pass.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Run local Flask server**

Run:

```powershell
python -m flask --app construction_maintenance run --debug --port 5000
```

Expected: server starts at `http://127.0.0.1:5000`.

- [ ] **Step 4: Browser verification**

Open:

```text
http://127.0.0.1:5000
```

Check:

- Dashboard hero and KPI cards render in the warm workbench style.
- Sidebar and header match the reference direction.
- Projects, people, qualifications, and modal views remain usable.
- Theme toggle still switches dark and light modes.
- No overlapping text or broken layout at desktop and mobile widths.

