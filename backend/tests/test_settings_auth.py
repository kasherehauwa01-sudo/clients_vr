from app.services.settings_auth import authenticate_settings, is_settings_authenticated, logout_settings


def test_settings_password_creates_and_revokes_session(monkeypatch) -> None:
    monkeypatch.setenv("SETTINGS_PASSWORD", "8852285")

    assert authenticate_settings("wrong") is None
    token = authenticate_settings("8852285")

    assert token is not None
    assert is_settings_authenticated(token)
    logout_settings(token)
    assert not is_settings_authenticated(token)
