"""
SportyFY - KPI Schemas

Purpose:
Defines the Pydantic models for data validation and API documentation 
related to Key Performance Indicators (KPIs).
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID

class KPIDefinitionBase(BaseModel):
    name: str
    category: str
    unit: str
    source_type: str
    tracking_type: str
    visualization: Optional[str] = 'line'  # 'line' | 'bar' | 'progress'
    linked_exercise_id: Optional[UUID] = None

class KPIDefinitionCreate(KPIDefinitionBase):
    user_id: Optional[UUID] = None

class KPIDefinitionResponse(KPIDefinitionBase):
    id: UUID
    user_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True

class KPITargetBase(BaseModel):
    kpi_id: UUID
    target_value: float
    target_mode: str
    cycle_period: Optional[str] = None
    start_date: date = Field(default_factory=date.today)
    end_date: Optional[date] = None
    is_pinned: bool = False

class KPITargetCreate(KPITargetBase):
    user_id: Optional[UUID] = None

class KPITargetResponse(KPITargetBase):
    id: UUID
    user_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class KPIMeasurementBase(BaseModel):
    kpi_id: UUID
    measured_value: float
    measured_at: datetime = Field(default_factory=datetime.now)
    source_reference: Optional[dict] = None

class KPIMeasurementCreate(KPIMeasurementBase):
    user_id: Optional[UUID] = None

class KPIMeasurementResponse(KPIMeasurementBase):
    id: UUID
    user_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class KPIDashboardItem(BaseModel):
    kpi_id: UUID
    name: str
    category: str
    unit: str
    visualization: str = 'line'  # 'line' | 'bar' | 'progress'
    target: Optional[KPITargetResponse] = None
    current_value: float = 0.0
    progress_percentage: float = 0.0
    trend_direction: str = "stable" # up, down, stable
    history: List[KPIMeasurementResponse] = []
