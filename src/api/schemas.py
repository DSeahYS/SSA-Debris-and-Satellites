from pydantic import BaseModel, Field
from typing import List, Optional, Any

# Standardized API Error schema
class APIErrorDetail(BaseModel):
    field: str
    message: str
    code: str

class APIError(BaseModel):
    code: str
    message: str
    details: Optional[List[APIErrorDetail]] = None

class ErrorResponse(BaseModel):
    error: APIError

# Standardized API Success schema
class SuccessResponse(BaseModel):
    data: Any
    meta: Optional[dict] = None
