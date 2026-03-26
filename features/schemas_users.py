"""
SportyFY - User Schemas

Purpose:
This module defines Pydantic models for user profile management.
"""

from pydantic import BaseModel
from typing import Optional

class UserProfileUpdate(BaseModel):
    """Schema for updating the user profile."""
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    birth_year: Optional[int] = None
    preferred_sport: Optional[str] = None
    is_debug_mode: Optional[bool] = None
