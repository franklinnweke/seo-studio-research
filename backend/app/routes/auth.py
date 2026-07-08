from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import AuthenticatedUser, require_authenticated_user
from app.schemas.responses import AuthUserResponse


router = APIRouter()


@router.get(
    "/me",
    response_model=AuthUserResponse,
    summary="Read authenticated user",
    description="Returns the Supabase user represented by the provided bearer token.",
)
def read_authenticated_user(
    user: Annotated[AuthenticatedUser | None, Depends(require_authenticated_user)],
) -> AuthUserResponse:
    if user is None:
        return AuthUserResponse(id="local-dev", email=None)
    return AuthUserResponse(id=user.id, email=user.email)
