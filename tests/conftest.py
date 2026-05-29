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
