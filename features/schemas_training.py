"""
SportyFY - Training & Workout Schemas

Purpose:
This module defines Pydantic models for training templates, exercises,
sessions, and workout logs. It captures the hierarchy of a workout plan.

Application Context:
Core schemas used for workout planning, execution, and historical tracking.

Data Flow:
Template (Blueprint) -> Session (Instance) -> Exercise Snapshot -> Session Logs (Results)
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime

# --- Enums matching DB ---

class VisibilityScope:
    """Visibility levels for templates."""
    private = "private"
    organization = "organization"
    public = "public"

class SessionStatus:
    """Status lifecycle of a training session."""
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    completed = "completed"
    missed = "missed"


# --- Template Exercises ---

class TemplateExerciseBase(BaseModel):
    """Specific exercise attached to a template with targets."""
    exercise_id: Optional[str] = None
    order_index: int
    group_id: Optional[str] = None
    group_name: Optional[str] = None
    target_sets: Optional[int] = 1
    target_reps: Optional[str] = None
    target_weight: Optional[float] = None
    target_rest_seconds: Optional[int] = None
    target_duration_seconds: Optional[int] = None
    interval_audio_cue: Optional[str] = None
    interval_visual_color: Optional[str] = None
    custom_name: Optional[str] = None
    custom_description: Optional[str] = None
    custom_image_url: Optional[str] = None
    custom_media_url: Optional[str] = None

class TemplateExerciseCreate(TemplateExerciseBase):
    """Schema to add an exercise to a template."""
    pass

class TemplateExerciseResponse(TemplateExerciseBase):
    """Template exercise details."""
    id: str
    template_id: str
    created_at: datetime


# --- Training Templates ---

class TrainingTemplateBase(BaseModel):
    """Blueprint for a workout plan."""
    title: str
    description: Optional[str] = None
    visibility: Optional[str] = "private"
    sport: Optional[str] = "Sonstiges"
    difficulty: Optional[str] = "Mittel"
    image_url: Optional[str] = None

class TrainingTemplateCreate(TrainingTemplateBase):
    """Schema to create a new template."""
    owner_id: Optional[str] = None

class TrainingTemplateResponse(TrainingTemplateBase):
    """Full template details as returned from the DB."""
    id: str
    owner_id: str
    org_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    exercises: Optional[List[TemplateExerciseResponse]] = None
    content_hash: Optional[str] = None


# --- Session Exercises ---

class SessionExerciseCreate(TemplateExerciseBase):
    """Schema for an exercise snapshot as part of an active session."""
    pass

class SessionExerciseResponse(TemplateExerciseBase):
    """Active session exercise details."""
    id: str
    session_id: str
    created_at: datetime
    model_config = {
        "from_attributes": True
    }


# --- Training Sessions ---

class TrainingSessionBase(BaseModel):
    """Instance of a template scheduled for a specific user."""
    template_id: Optional[str] = None
    scheduled_date: Optional[date] = None
    scheduled_time: Optional[str] = None  # HH:MM format
    status: Optional[str] = "pending"
    image_url: Optional[str] = None

class TrainingSessionCreate(TrainingSessionBase):
    """Schema to schedule a new session."""
    title: Optional[str] = None
    description: Optional[str] = None
    exercises: Optional[List[TemplateExerciseCreate]] = None
    youtube_url: Optional[str] = None
    youtube_urls: Optional[List[str]] = None
    assigned_by: Optional[str] = None

class TrainingSessionUpdate(BaseModel):
    """Schema for partially updating an existing session."""
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_date: Optional[date] = None
    scheduled_time: Optional[str] = None
    sport: Optional[str] = None
    difficulty: Optional[str] = None
    image_url: Optional[str] = None

class TrainingSessionResponse(TrainingSessionBase):
    """Full session details including completion metadata."""
    id: str
    trainee_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    sport: Optional[str] = "Sonstiges"
    difficulty: Optional[str] = "Mittel"
    assigned_by: Optional[str] = None
    feedback_rpe: Optional[int] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    exercises: Optional[List[SessionExerciseResponse]] = None
    content_hash: Optional[str] = None

class SessionComplete(BaseModel):
    """Schema for marking a session finished with user feedback."""
    feedback_rpe: int = Field(ge=1, le=10, description="Rate of perceived exertion (1-10)")

class UpcomingSessionResponse(BaseModel):
    """Richer response model specifically for Dashboard cards."""
    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    sport: Optional[str] = "Sonstiges"
    difficulty: Optional[str] = "Mittel"
    scheduled_date: Optional[date] = None
    scheduled_time: Optional[str] = None
    status: str
    template_id: Optional[str] = None
    is_trainer_assigned: bool = False
    trainee_id: str
    image_url: Optional[str] = None
    created_at: datetime


# --- Session Logs (Sets) ---

class SessionLogBase(BaseModel):
    """Actual performance data for a single set of an exercise."""
    set_number: int
    actual_reps: Optional[int] = None
    actual_weight: Optional[float] = None
    actual_duration_seconds: Optional[int] = None

class SessionLogCreate(SessionLogBase):
    """Schema for logging a completed set."""
    pass

class SessionLogResponse(SessionLogBase):
    """Workout log entry details."""
    id: str
    session_exercise_id: str
    created_at: datetime


# --- KPI Tracking ---

class KPISummaryResponse(BaseModel):
    """Aggregated volume metrics for a user."""
    total_workouts_completed: int
    total_volume_kg: float

class ExerciseProgressResponse(BaseModel):
    """Progression data for a specific exercise over time."""
    session_date: datetime
    max_weight: float
