from __future__ import annotations

from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from construction_maintenance import create_app
from construction_maintenance.security import safe_redirect_target


@pytest.fixture()
def secure_app(tmp_path: Path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": tmp_path / "test.sqlite3",
            "UPLOAD_FOLDER": tmp_path / "uploads",
            "SECRET_KEY": "test-secret",
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD_HASH": generate_password_hash("correct-password"),
            "AUTH_REQUIRED": True,
            "CSRF_ENABLED": True,
        }
    )


@pytest.fixture()
def secure_client(secure_app):
    return secure_app.test_client()


def _csrf_token(client) -> str:
    with client.session_transaction() as session:
        return session["csrf_token"]


def test_auth_configuration_is_required(tmp_path: Path):
    with pytest.raises(RuntimeError, match="CAM_SECRET_KEY"):
        create_app(
            {
                "DATABASE": tmp_path / "test.sqlite3",
                "UPLOAD_FOLDER": tmp_path / "uploads",
                "AUTH_REQUIRED": True,
                "SECRET_KEY": "dev",
            }
        )


def test_unauthenticated_requests_are_blocked(secure_client):
    response = secure_client.get("/", base_url="https://localhost")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login?next=/")

    response = secure_client.post("/projects", base_url="https://localhost")
    assert response.status_code == 401


def test_login_requires_csrf_and_valid_credentials(secure_client):
    response = secure_client.get("/login", base_url="https://localhost")
    assert response.status_code == 200
    assert "建筑工程维护系统".encode() in response.data
    assert 'name="username"'.encode() in response.data
    assert 'name="password"'.encode() in response.data
    assert "login-password-toggle".encode() in response.data
    assert "login-showcase.png".encode() in response.data
    showcase = secure_client.get(
        "/static/login-showcase.png", base_url="https://localhost"
    )
    assert showcase.status_code == 200
    assert showcase.content_type == "image/png"
    cookie = response.headers["Set-Cookie"]
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie

    response = secure_client.post(
        "/login",
        data={"username": "admin", "password": "correct-password"},
        base_url="https://localhost",
    )
    assert response.status_code == 400

    token = _csrf_token(secure_client)
    response = secure_client.post(
        "/login",
        data={
            "username": "admin",
            "password": "wrong-password",
            "_csrf": token,
        },
        base_url="https://localhost",
    )
    assert response.status_code == 401

    response = secure_client.post(
        "/login?next=/people",
        data={
            "username": "admin",
            "password": "correct-password",
            "_csrf": token,
        },
        base_url="https://localhost",
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/people")
    with secure_client.session_transaction() as session:
        assert session["authenticated"] is True
        assert session["csrf_token"] != token


def test_logout_requires_csrf(secure_client):
    secure_client.get("/login", base_url="https://localhost")
    token = _csrf_token(secure_client)
    secure_client.post(
        "/login",
        data={
            "username": "admin",
            "password": "correct-password",
            "_csrf": token,
        },
        base_url="https://localhost",
    )

    response = secure_client.post("/logout", base_url="https://localhost")
    assert response.status_code == 400

    token = _csrf_token(secure_client)
    response = secure_client.post(
        "/logout",
        data={"_csrf": token},
        base_url="https://localhost",
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with secure_client.session_transaction() as session:
        assert "authenticated" not in session


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("/people", "/people"),
        ("https://localhost/people?view=all", "/people?view=all"),
        ("https://example.com", "/"),
        ("//example.com", "/"),
        (r"/\example.com", "/"),
        ("people", "/"),
        (None, "/"),
    ],
)
def test_safe_redirect_target(secure_app, candidate, expected):
    with secure_app.test_request_context("/", base_url="https://localhost"):
        assert safe_redirect_target(candidate, "/") == expected
