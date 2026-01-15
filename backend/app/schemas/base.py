"""
Schema base para todos os schemas do MedSafe
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID


class BaseSchema(BaseModel):
    """Schema base com campos comuns"""

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}


class TimestampSchema(BaseSchema):
    """Schema com campos de timestamp"""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class IDSchema(BaseSchema):
    """Schema com campo de ID"""

    id: UUID = Field(..., description="ID único do registro")
