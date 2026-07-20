from __future__ import annotations

import time
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from construction_maintenance import create_app
from construction_maintenance import repositories as repo
from construction_maintenance.db import get_db


SUPER_PASSWORD = "CorrectPassword#123"
ADMIN_PASSWORD = "InitialPassword#123"


@pytest.fixture()
def settings_app(tmp_path: Path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": tmp_path / "settings.sqlite3",
            "UPLOAD_FOLDER": tmp_path / "uploads",
            "SECRET_KEY": "settings-test-secret",
            "ADMIN_USERNAME": "owner",
            "ADMIN_PASSWORD_HASH": generate_password_hash(SUPER_PASSWORD),
            "AUTH_REQUIRED": True,
            "CSRF_ENABLED": True,
        }
    )


def csrf_token(client) -> str:
    with client.session_transaction() as session:
        return session["csrf_token"]


def login(client, username: str, password: str):
    client.get("/login", base_url="https://localhost")
    return client.post(
        "/login",
        data={
            "username": username,
            "password": password,
            "_csrf": csrf_token(client),
        },
        base_url="https://localhost",
    )


def create_admin(
    app,
    *,
    username: str = "operator",
    role: str = "admin",
    is_active: bool = True,
) -> int:
    with app.app_context():
        return repo.create_admin_user(
            {
                "username": username,
                "display_name": "项目管理员",
                "password": ADMIN_PASSWORD,
                "role": role,
                "is_active": is_active,
            }
        )


def test_settings_requires_an_admin_context_when_auth_is_disabled(client):
    assert client.get("/settings").status_code == 403


def test_bootstrap_account_is_active_super_admin(settings_app):
    with settings_app.app_context():
        user = repo.get_admin_user_by_username("owner")

    assert user is not None
    assert user["display_name"] == "系统管理员"
    assert user["role"] == "super_admin"
    assert user["is_active"] == 1
    assert user["must_change_password"] == 0


def test_super_admin_can_view_all_settings_tabs(settings_app):
    client = settings_app.test_client()
    assert login(client, "owner", SUPER_PASSWORD).status_code == 302

    response = client.get(
        "/settings?tab=admins", base_url="https://localhost"
    )

    assert response.status_code == 200
    assert "账号安全".encode() in response.data
    assert "管理员账号".encode() in response.data
    assert "基本设置".encode() in response.data
    assert "新增管理员".encode() in response.data


def test_admin_creation_duplicate_and_forced_password_change(settings_app):
    client = settings_app.test_client()
    login(client, "owner", SUPER_PASSWORD)
    payload = {
        "username": "operator",
        "display_name": "项目管理员",
        "password": ADMIN_PASSWORD,
        "confirm_password": ADMIN_PASSWORD,
        "role": "admin",
        "is_active": "1",
        "_csrf": csrf_token(client),
    }

    response = client.post(
        "/settings/admins",
        data=payload,
        base_url="https://localhost",
    )
    assert response.status_code == 302

    payload["_csrf"] = csrf_token(client)
    response = client.post(
        "/settings/admins",
        data=payload,
        follow_redirects=True,
        base_url="https://localhost",
    )
    assert "该管理员用户名已存在".encode() in response.data

    operator = settings_app.test_client()
    response = login(operator, "operator", ADMIN_PASSWORD)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/settings?tab=security")
    with settings_app.app_context():
        assert repo.get_admin_user_by_username("operator")[
            "must_change_password"
        ] == 1


def test_own_password_change_rejects_old_password(settings_app):
    client = settings_app.test_client()
    login(client, "owner", SUPER_PASSWORD)
    new_password = "UpdatedPassword#456"

    response = client.post(
        "/settings/password",
        data={
            "current_password": SUPER_PASSWORD,
            "new_password": new_password,
            "confirm_password": new_password,
            "_csrf": csrf_token(client),
        },
        base_url="https://localhost",
    )
    assert response.status_code == 302

    old_client = settings_app.test_client()
    assert login(old_client, "owner", SUPER_PASSWORD).status_code == 401
    new_client = settings_app.test_client()
    assert login(new_client, "owner", new_password).status_code == 302


def test_disabled_account_is_rejected_and_existing_session_is_invalidated(
    settings_app,
):
    operator_id = create_admin(settings_app)
    operator = settings_app.test_client()
    assert login(operator, "operator", ADMIN_PASSWORD).status_code == 302

    with settings_app.app_context():
        owner = repo.get_admin_user_by_username("owner")
        repo.update_admin_user(
            operator_id,
            {
                "display_name": "项目管理员",
                "role": "admin",
                "is_active": False,
            },
            actor_id=owner["id"],
        )

    response = operator.get("/", base_url="https://localhost")
    assert response.status_code == 302
    assert "/login?next=/" in response.headers["Location"]
    with operator.session_transaction() as session:
        assert "authenticated" not in session

    fresh_client = settings_app.test_client()
    assert login(fresh_client, "operator", ADMIN_PASSWORD).status_code == 401


def test_normal_admin_cannot_manage_accounts_or_general_settings(settings_app):
    create_admin(settings_app)
    client = settings_app.test_client()
    login(client, "operator", ADMIN_PASSWORD)

    response = client.get(
        "/settings?tab=admins", base_url="https://localhost"
    )
    assert response.status_code == 200
    assert "新增管理员".encode() not in response.data

    response = client.post(
        "/settings/general",
        data={
            "system_name": "无权修改",
            "session_timeout_minutes": "120",
            "_csrf": csrf_token(client),
        },
        base_url="https://localhost",
    )
    assert response.status_code == 403


def test_last_active_super_admin_cannot_be_disabled_or_demoted(settings_app):
    with settings_app.app_context():
        owner = repo.get_admin_user_by_username("owner")
        with pytest.raises(ValueError, match="至少一名"):
            repo.update_admin_user(
                owner["id"],
                {
                    "display_name": owner["display_name"],
                    "role": "admin",
                    "is_active": True,
                },
                actor_id=999,
            )

        second_id = repo.create_admin_user(
            {
                "username": "backup-owner",
                "display_name": "备用超级管理员",
                "password": ADMIN_PASSWORD,
                "role": "super_admin",
                "is_active": True,
            }
        )
        repo.update_admin_user(
            owner["id"],
            {
                "display_name": owner["display_name"],
                "role": "admin",
                "is_active": True,
            },
            actor_id=second_id,
        )
        assert repo.get_admin_user(owner["id"])["role"] == "admin"


def test_general_settings_persist_and_validate_timeout(settings_app):
    client = settings_app.test_client()
    login(client, "owner", SUPER_PASSWORD)

    response = client.post(
        "/settings/general",
        data={
            "system_name": "工程维护中台",
            "organization_name": "华东工程中心",
            "support_contact": "ops@example.com",
            "session_timeout_minutes": "60",
            "_csrf": csrf_token(client),
        },
        base_url="https://localhost",
    )
    assert response.status_code == 302
    with settings_app.app_context():
        settings = repo.get_system_settings()
    assert settings["system_name"] == "工程维护中台"
    assert settings["organization_name"] == "华东工程中心"
    assert settings["support_contact"] == "ops@example.com"
    assert settings["session_timeout_minutes"] == "60"

    response = client.post(
        "/settings/general",
        data={
            "system_name": "不应保存",
            "session_timeout_minutes": "5",
            "_csrf": csrf_token(client),
        },
        follow_redirects=True,
        base_url="https://localhost",
    )
    assert "15 至 1440 分钟".encode() in response.data
    with settings_app.app_context():
        assert repo.get_system_setting("system_name") == "工程维护中台"


def test_expired_session_redirects_to_login(settings_app):
    client = settings_app.test_client()
    login(client, "owner", SUPER_PASSWORD)
    with settings_app.app_context():
        repo.update_system_settings({"session_timeout_minutes": "15"})
    with client.session_transaction() as session:
        session["last_activity_at"] = int(time.time()) - (16 * 60)

    response = client.get("/projects", base_url="https://localhost")

    assert response.status_code == 302
    assert "/login?next=/projects" in response.headers["Location"]


def test_password_reset_invalidates_old_password_and_requires_change(settings_app):
    operator_id = create_admin(settings_app)
    owner = settings_app.test_client()
    login(owner, "owner", SUPER_PASSWORD)
    reset_password = "ResetPassword#789"

    response = owner.post(
        f"/settings/admins/{operator_id}/reset-password",
        data={
            "password": reset_password,
            "confirm_password": reset_password,
            "_csrf": csrf_token(owner),
        },
        base_url="https://localhost",
    )
    assert response.status_code == 302

    old_client = settings_app.test_client()
    assert login(old_client, "operator", ADMIN_PASSWORD).status_code == 401
    reset_client = settings_app.test_client()
    response = login(reset_client, "operator", reset_password)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/settings?tab=security")
    with settings_app.app_context():
        row = get_db().execute(
            "select must_change_password from admin_users where id = ?",
            (operator_id,),
        ).fetchone()
        assert row["must_change_password"] == 1
