from typing import Optional
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail