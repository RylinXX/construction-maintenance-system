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
    assert "nav-submenu" in base_html
    assert "nav-subitem" in base_html


def test_dashboard_uses_workbench_hero():
    dashboard_html = read_text("construction_maintenance/templates/dashboard.html")

    assert "dashboard-hero" in dashboard_html
    assert "dashboard-hero-panel" in dashboard_html


def test_document_previews_support_legacy_pdf_upload_names():
    qualifications_html = read_text("construction_maintenance/templates/qualifications.html")
    people_html = read_text("construction_maintenance/templates/people.html")

    assert "isPdfPreviewFile" in qualifications_html
    assert "endsWith('_pdf')" in qualifications_html
    assert "isPdfIdCard" in people_html
    assert "endsWith('_pdf')" in people_html
