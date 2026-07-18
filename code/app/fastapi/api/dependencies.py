from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings

bearer_scheme = HTTPBearer()


def verify_internal_token(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> None:
    """
    Validates the Bearer token for internal endpoints.
    Raises HTTP 401 if token does not match settings.secret_key.
    """
    if credentials.credentials != settings.secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Invalid or missing token.",
            },
        )