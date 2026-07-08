import pytest
from fastapi import HTTPException

from app.auth import is_auth_enabled, require_authenticated_user
from app.config import Settings


def test_auth_is_disabled_without_supabase_config() -> None:
    settings = Settings(
        supabase_url="",
        supabase_jwt_issuer="",
        supabase_jwks_url="",
    )

    assert not is_auth_enabled(settings)
    assert require_authenticated_user(credentials=None, settings=settings) is None


def test_auth_requires_bearer_token_when_supabase_is_configured() -> None:
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_jwt_issuer="https://example.supabase.co/auth/v1",
        supabase_jwks_url="https://example.supabase.co/auth/v1/.well-known/jwks.json",
    )

    assert is_auth_enabled(settings)
    with pytest.raises(HTTPException) as exc:
        require_authenticated_user(credentials=None, settings=settings)

    assert exc.value.status_code == 401
