"""
SportyFY - User Metrics & Goals Schemas

Purpose:
This module defines Pydantic models for body metrics, user goals, and dashboard preferences.
These schemas ensure data integrity between the API and the Supabase database.

Application Context:
Shared across the metrics feature module for request validation and response formatting.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import datetime
from uuid import UUID

# --- Body Metrics ---

class BodyMetricBase(BaseModel):
    """Base fields for a body measurement entry."""
    weight_kg: Optional[float] = Field(None, description="Weight in kilograms")
    body_fat_percent: Optional[float] = Field(None, description="Body fat percentage")
    notes: Optional[str] = Field(None, description="Optional notes for the entry")
    date: Optional[datetime.date] = Field(default_factory=datetime.date.today, description="Date of the measurement")

class BodyMetricCreate(BodyMetricBase):
    """Schema for creating a new body metric entry."""
    pass

class BodyMetricResponse(BodyMetricBase):
    """Schema for the body metric response, including database-generated fields."""
    id: UUID
    user_id: UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {
        "from_attributes": True
    }

# --- User Goals ---

class UserGoalBase(BaseModel):
    """Base fields for user-defined fitness targets."""
    target_weight_kg: Optional[float] = Field(None, description="Target weight in kilograms")
    target_body_fat_percent: Optional[float] = Field(None, description="Target body fat percentage")
    target_weekly_workouts: Optional[int] = Field(None, description="Target number of workouts per week")

class UserGoalCreate(UserGoalBase):
    """Schema for creating user goals."""
    pass

class UserGoalUpdate(UserGoalBase):
    """Schema for updating user goals."""
    pass

class UserGoalResponse(UserGoalBase):
    """Schema for the user goal response, including database-generated fields."""
    id: UUID
    user_id: UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {
        "from_attributes": True
    }

# --- User Preferences (Dashboard Layout) ---

class UserPreferencesBase(BaseModel):
    """Base fields for frontend-specific user settings."""
    dashboard_layout: List[Dict[str, Any]] = Field(default_factory=list, description="JSON array representing KPI tile order/visibility")

class UserPreferencesUpdate(UserPreferencesBase):
    """Schema for updating user preferences."""
    pass

class UserPreferencesResponse(UserPreferencesBase):
    """Schema for the user preferences response."""
    id: UUID
    user_id: UUID
    updated_at: datetime.datetime

    model_config = {
        "from_attributes": True
    }

