import os
import secrets
from threading import Lock

COOKIE_NAME = "clients_settings_session"
_sessions: set[str] = set()
_lock = Lock()


def authenticate_settings(password: str) -> str | None:
    expected = os.getenv("SETTINGS_PASSWORD", "8852285")
    if not expected or not secrets.compare_digest(password, expected):
        return None
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions.add(token)
    return token


def is_settings_authenticated(token: str | None) -> bool:
    if not token:
        return False
    with _lock:
        return token in _sessions


def logout_settings(token: str | None) -> None:
    if token:
        with _lock:
            _sessions.discard(token)
