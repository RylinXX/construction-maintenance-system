from __future__ import annotations

import hmac
import secrets
from urllib.parse import urlsplit

from flask import abort, current_app, redirect, request, session, url_for
from werkzeug.security import check_password_hash


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
PUBLIC_ENDPOINTS = {"web.login", "static"}


def get_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def safe_redirect_target(candidate: str | None, fallback: str) -> str:
    if not candidate:
        return fallback
    if "\\" in candidate or any(ord(char) < 32 for char in candidate):
        return fallback

    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc:
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.netloc.casefold() != request.host.casefold()
        ):
            return fallback
        candidate = parsed.path or "/"
        if parsed.query:
            candidate = f"{candidate}?{parsed.query}"

    if not candidate.startswith("/") or candidate.startswith("//"):
        return fallback
    return candidate


def credentials_valid(username: str, password: str) -> bool:
    expected_user = current_app.config.get("ADMIN_USERNAME", "")
    password_hash = current_app.config.get("ADMIN_PASSWORD_HASH", "")
    return bool(
        expected_user
        and password_hash
        and hmac.compare_digest(username, expected_user)
        and check_password_hash(password_hash, password)
    )


def login_user() -> None:
    session.clear()
    session["authenticated"] = True
    session["csrf_token"] = secrets.token_urlsafe(32)


def logout_user() -> None:
    session.clear()


def _protect_request():
    endpoint = request.endpoint
    public = endpoint in PUBLIC_ENDPOINTS

    if current_app.config.get("AUTH_REQUIRED", True) and not public:
        if not session.get("authenticated"):
            if request.method in SAFE_METHODS:
                target = request.full_path.rstrip("?")
                return redirect(url_for("web.login", next=target))
            abort(401)

    if current_app.config.get("CSRF_ENABLED", True) and request.method not in SAFE_METHODS:
        expected = session.get("csrf_token", "")
        supplied = request.form.get("_csrf", "") or request.headers.get(
            "X-CSRF-Token", ""
        )
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            abort(400, description="CSRF validation failed")
    return None


def init_app(app) -> None:
    app.before_request(_protect_request)
    app.jinja_env.globals["csrf_token"] = get_csrf_token
