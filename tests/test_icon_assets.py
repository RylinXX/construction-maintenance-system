from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "construction_maintenance" / "templates"
ICON_DIR = ROOT / "construction_maintenance" / "static" / "icons"

EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]")

ICON_NAMES = {
    "add",
    "ai",
    "back",
    "bank-card",
    "checklist",
    "company",
    "dashboard",
    "document",
    "download",
    "edit",
    "empty-inbox",
    "error",
    "export",
    "folder",
    "hardhat",
    "home",
    "id-card",
    "import",
    "inbox",
    "money",
    "people",
    "preview",
    "print",
    "qualification",
    "receipt",
    "rotate",
    "save",
    "search",
    "success",
    "trend",
    "upload",
    "zoom-in",
    "zoom-out",
}


def test_templates_do_not_use_emoji_symbols():
    offenders: list[str] = []

    for template in sorted(TEMPLATE_DIR.glob("*.html")):
        text = template.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if EMOJI_RE.search(line):
                offenders.append(f"{template.name}:{line_no}: {line.strip()}")

    assert not offenders, "Emoji symbols remain in templates:\n" + "\n".join(offenders)


def test_generated_icon_assets_are_available():
    missing = [name for name in sorted(ICON_NAMES) if not (ICON_DIR / f"{name}.png").exists()]

    assert not missing, "Missing generated icon assets: " + ", ".join(missing)


def test_qualification_card_actions_use_compact_icon_button_layout():
    template = (TEMPLATE_DIR / "qualifications.html").read_text(encoding="utf-8")

    assert 'class="card-actions qualification-actions"' in template
    assert 'class="btn btn-secondary card-btn qualification-preview-btn"' in template
    assert "预览下载" in template
