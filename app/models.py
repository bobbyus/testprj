from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class EmailOutput(BaseModel):
    # 'from' is a reserved keyword in Python; use alias
    from_: Optional[str] = Field(default=None, alias="from")
    to: List[str] = Field(default_factory=list)
    subject: Optional[str] = None
    text: Optional[str] = None
    date: Optional[str] = None  # RFC 3339 preferred
    message_id: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
        populate_by_name = True
