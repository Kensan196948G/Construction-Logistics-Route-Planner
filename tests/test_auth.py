from __future__ import annotations

from starlette.requests import Request

from app.auth import _api_key_auth


def _request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/projects",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def test_api_key_mode_ignores_spoofed_identity_headers(monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "secret-key-123456")
    request = _request({"x-user-id": "admin", "x-user-role": "admin"})

    user = _api_key_auth(request, "Bearer secret-key-123456")

    # Client-supplied headers must not become audit identity.
    assert user.user_id == "api-key-operator"
    assert user.role == "planner"


def test_anonymous_mode_does_not_trust_headers(monkeypatch) -> None:
    monkeypatch.delenv("APP_API_KEY", raising=False)
    request = _request({"x-user-id": "admin", "x-user-role": "admin"})

    user = _api_key_auth(request, None)

    assert user.user_id == "anonymous"
    assert user.role == "planner"


def test_api_key_mode_uses_configured_identity(monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "secret-key-123456")
    monkeypatch.setenv("APP_API_KEY_USER_ID", "kensan")
    monkeypatch.setenv("APP_API_KEY_USER_ROLE", "site_user")
    request = _request({"x-user-id": "spoofed"})

    user = _api_key_auth(request, "Bearer secret-key-123456")

    assert user.user_id == "kensan"
    assert user.role == "site_user"
