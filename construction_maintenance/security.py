from __future__ import annotations

from functools import wraps
import hmac
import secrets
import time
from urllib.parse import urlsplit

from flask import abort, current_app, g, redirect, request, session, url_for

from . import repositories as repo


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
    return authenticate_user(username, password) is not None


def authenticate_user(username: str, password: str):
    return repo.authenticate_admin_user(username, password)


def login_user(user) -> None:
    session.clear()
    session["authenticated"] = True
    session["admin_user_id"] = int(user["id"])
    session["last_activity_at"] = int(time.time())
    session["csrf_token"] = secrets.token_urlsafe(32)


def logout_user() -> None:
    session.clear()


def get_current_admin():
    return getattr(g, "admin_user", None)


def require_admin(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_current_admin() is None:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def require_super_admin(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_admin()
        if user is None or user["role"] != "super_admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def _authentication_failure():
    session.clear()
    if request.method in SAFE_METHODS:
        target = request.full_path.rstrip("?")
        return redirect(url_for("web.login", next=target))
    abort(401)


def _protect_request():
    endpoint = request.endpoint
    public = endpoint in PUBLIC_ENDPOINTS
    g.admin_user = None

    if current_app.config.get("AUTH_REQUIRED", True) and not public:
        user_id = session.get("admin_user_id")
        if not session.get("authenticated") or not user_id:
            return _authentication_failure()

        user = repo.get_admin_user(int(user_id))
        if user is None or not user["is_active"]:
            return _authentication_failure()

        try:
            timeout_minutes = int(
                repo.get_system_setting("session_timeout_minutes")
            )
        except (TypeError, ValueError):
            timeout_minutes = 120
        now = int(time.time())
        last_activity_at = session.get("last_activity_at")
        if (
            not isinstance(last_activity_at, (int, float))
            or now - last_activity_at > timeout_minutes * 60
        ):
            return _authentication_failure()

        session["last_activity_at"] = now
        g.admin_user = user

        password_change_endpoints = {
            "web.settings",
            "web.change_password",
            "web.logout",
        }
        if user["must_change_password"] and endpoint not in password_change_endpoints:
            if request.method in SAFE_METHODS:
                return redirect(url_for("web.settings", tab="security"))
            abort(403)

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

    @app.context_processor
    def inject_system_context():
        return {
            "current_admin": get_current_admin(),
            "system_settings": repo.get_system_settings(),
        }
