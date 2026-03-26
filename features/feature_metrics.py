"""
SportyFY - User Metrics & Goals Feature

Purpose:
This module provides endpoints for tracking body metrics (weight, body fat), 
setting fitness goals, and managing user-specific frontend preferences.

Application Context:
Core feature module for the Dashboard and Profile sections of the app.
Directly interacts with 'body_metrics', 'user_goals', and 'user_preferences' tables.

Data Flow:
User Input -> feature_metrics.py (Validation/Formatting) -> Supabase DB -> Response
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from supabase import Client
from database import get_supabase
from dependencies import get_current_user
from .schemas_metrics import (
    BodyMetricCreate, BodyMetricResponse,
    UserGoalCreate, UserGoalUpdate, UserGoalResponse,
    UserPreferencesUpdate, UserPreferencesResponse
)
import logging

# Configure logger for this module
logger = logging.getLogger(__name__)

router = APIRouter()

# -------------------------------------------------------------------
# BODY METRICS ENDPOINTS
# -------------------------------------------------------------------

@router.post("/metrics/", response_model=BodyMetricResponse, status_code=status.HTTP_201_CREATED)
def log_body_metric(
    metric_in: BodyMetricCreate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Log a new body metric entry (weight, body fat).
    
    Args:
        metric_in (BodyMetricCreate): Measurement data.
        current_user (dict): Authenticated user.
        supabase (Client): DB client.
        
    Returns:
        BodyMetricResponse: The newly created record.
        
    Side Effects:
        - Inserts a row into the 'body_metrics' table.
    """
    user_id = current_user.get("id")
    
    insert_data = metric_in.model_dump(exclude_unset=True)
    insert_data["user_id"] = user_id
    # Convert date to string for Supabase JSON serialization
    if "date" in insert_data and insert_data["date"]:
        insert_data["date"] = insert_data["date"].isoformat()

    try:
        response = supabase.table("body_metrics").insert(insert_data).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to log metric.")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics/", response_model=List[BodyMetricResponse])
def get_body_metrics(
    limit: int = 30,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Get historical body metrics for the current user.
    
    Args:
        limit (int): Number of entries to retrieve (default 30).
        current_user (dict): Authenticated user.
        supabase (Client): DB client.
        
    Returns:
        List[BodyMetricResponse]: List of historical measurements ordered by date DESC.
    """
    user_id = current_user.get("id")
    try:
        response = supabase.table("body_metrics").select("*").eq("user_id", user_id).order("date", desc=True).limit(limit).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------------------------------------------
# USER GOALS ENDPOINTS
# -------------------------------------------------------------------

@router.get("/goals/", response_model=UserGoalResponse)
def get_user_goals(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Retrieve the current user's fitness targets and goals.
    
    Args:
        current_user (dict): The authenticated user.
        supabase (Client): Injected Supabase client.
        
    Returns:
        UserGoalResponse: The user's goals or a default skeleton if no goals have been set yet.
        
    Side Effects:
        - Executes a SELECT query on the 'user_goals' table.
    """
    user_id = current_user.get("id")
    logger.info(f"Fetching goals for user: {user_id}")
    try:
        response = supabase.table("user_goals").select("*").eq("user_id", user_id).execute()
        if not response.data:
            # Return empty skeleton if none found instead of 404 to simplify frontend
            return {
                "id": "00000000-0000-0000-0000-000000000000",
                "user_id": user_id,
                "target_weight_kg": None,
                "target_body_fat_percent": None,
                "target_weekly_workouts": None,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z"
            }
        return response.data[0]
    except Exception as e:
        logger.error(f"Error in get_user_goals: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/goals/", response_model=UserGoalResponse)
def upsert_user_goals(
    goals_in: UserGoalUpdate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Create or update the user's target goals.
    
    Args:
        goals_in (UserGoalUpdate): New goal data.
        
    Returns:
        UserGoalResponse: The updated record.
    """
    user_id = current_user.get("id")
    upsert_data = goals_in.model_dump(exclude_unset=True)
    upsert_data["user_id"] = user_id

    try:
        # Use upsert to handle both creation and updates using the unique user_id constraint
        response = supabase.table("user_goals").upsert(upsert_data, on_conflict="user_id").execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to save goals.")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------------------------------------------
# USER PREFERENCES (DASHBOARD) ENDPOINTS
# -------------------------------------------------------------------

@router.get("/preferences/", response_model=UserPreferencesResponse)
def get_user_preferences(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Retrieve the current user's UI preferences, such as dashboard layout and tile order.
    
    Args:
        current_user (dict): The authenticated user.
        supabase (Client): Injected Supabase client.
        
    Returns:
        UserPreferencesResponse: The user's preference record or a default fallback if none exists.
        
    Side Effects:
        - Executes a SELECT query on the 'user_preferences' table.
    """
    user_id = current_user.get("id")
    try:
        response = supabase.table("user_preferences").select("*").eq("user_id", user_id).execute()
        # Default fallback for new users who haven't customized their dashboard yet.
        if not response.data:
            return {
                "id": "00000000-0000-0000-0000-000000000000",
                "user_id": user_id,
                "dashboard_layout": [],
                "updated_at": "2026-01-01T00:00:00Z"
            }
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/preferences/", response_model=UserPreferencesResponse)
def update_user_preferences(
    prefs_in: UserPreferencesUpdate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Update user preferences (like dragged KPI tile order or visibility).
    
    Args:
        prefs_in (UserPreferencesUpdate): Partial layout updates.
        
    Returns:
        UserPreferencesResponse: The updated preference record.
    """
    user_id = current_user.get("id")
    upsert_data = prefs_in.model_dump(exclude_unset=True)
    upsert_data["user_id"] = user_id

    try:
        # Persistence for frontend UI state (e.g. tile order).
        response = supabase.table("user_preferences").upsert(upsert_data, on_conflict="user_id").execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to save preferences.")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
