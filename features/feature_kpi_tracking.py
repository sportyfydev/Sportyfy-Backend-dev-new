"""
SportyFY - KPI Tracking Feature

Purpose:
This module provides endpoints for analyzing completed training sessions 
and aggregating performance data (Volume, Frequency, Progress) for the 
frontend dashboard and analytics views.

Application Context:
Analytics layer for the Trainee dashboard.
Interacts with 'training_sessions', 'session_exercises', and 'session_logs' tables.

Data Flow:
Trainee Dashboard -> feature_kpi_tracking.py -> Data Aggregation (Python) -> Response
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from database import get_supabase
from supabase import Client
from dependencies import get_current_user
from .schemas_training import (
    KPISummaryResponse, ExerciseProgressResponse
)
import logging

# Configure logger
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/summary", response_model=KPISummaryResponse)
def get_kpi_summary(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Retrieve high-level KPIs for the authenticated user based on completed sessions.
    
    Args:
        current_user (dict): The authenticated trainee.
        supabase (Client): Injected Supabase client.
        
    Returns:
        KPISummaryResponse: Aggregated stats including total workouts and lifting volume.
        
    Side Effects:
        - Performs multiple sequential database queries to calculate aggregate volume.
    """
    try:
        user_id = current_user.get("id")
        
        # 1. Fetch completed sessions count.
        sessions_res = supabase.table("training_sessions") \
            .select("id") \
            .eq("trainee_id", user_id) \
            .eq("status", "completed") \
            .execute()
        
        total_workouts = len(sessions_res.data) if sessions_res.data else 0
        
        # 2. Calculate Total Volume.

        # Since Supabase python client (v2) doesn't support complex cross-table SUM joins easily 
        # in a single call without RPC, we perform a multi-step aggregation.
        total_volume_kg = 0.0
        
        if total_workouts > 0:
            # Map session IDs to fetch associated exercise snapshots.
            session_ids = [s["id"] for s in sessions_res.data]
            
            exercises_res = supabase.table("session_exercises") \
                .select("id") \
                .in_("session_id", session_ids) \
                .execute()
                
            if exercises_res.data:
                # Map exercise snapshots to fetch actual performance logs.
                ex_ids = [e["id"] for e in exercises_res.data]
                
                logs_res = supabase.table("session_logs") \
                    .select("actual_reps,actual_weight") \
                    .in_("session_exercise_id", ex_ids) \
                    .execute()
                    
                # Aggregate Volume (Sets * Reps * Weight).
                for log in logs_res.data:
                    reps = log.get("actual_reps") or 0
                    weight = log.get("actual_weight") or 0.0
                    total_volume_kg += (reps * weight)
                    
        return KPISummaryResponse(
            total_workouts_completed=total_workouts,
            total_volume_kg=total_volume_kg
        )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch KPI summary: {str(e)}")

@router.get("/exercise/{exercise_id}", response_model=List[ExerciseProgressResponse])
def get_exercise_progress(
    exercise_id: str, 
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Retrieve progress history for a specific exercise (e.g. tracking Max Weight over time).
    
    Args:
        exercise_id (str): The specific exercise in the content library to track.
        current_user (dict): The authenticated user.
        supabase (Client): Injected Supabase client.
        
    Returns:
        List[ExerciseProgressResponse]: A chronological list of performance data points.
    """
    try:
        user_id = current_user.get("id")
        
        # 1. Identify all completed sessions.
        sessions_res = supabase.table("training_sessions") \
            .select("id, completed_at") \
            .eq("trainee_id", user_id) \
            .eq("status", "completed") \
            .execute()
            
        if not sessions_res.data:
            return []
            
        # Create a mapping of Session ID -> Completion Date.
        session_map = {s["id"]: s.get("completed_at") for s in sessions_res.data}
        session_ids = list(session_map.keys())
        
        # 2. Get exercise snapshots for this specific exercise within those sessions.
        exercises_res = supabase.table("session_exercises") \
            .select("id, session_id") \
            .eq("exercise_id", exercise_id) \
            .in_("session_id", session_ids) \
            .execute()
            
        if not exercises_res.data:
            return []
            
        # Create mapping of Exercise Instance -> Completion Date.
        ex_map = {e["id"]: session_map.get(e["session_id"]) for e in exercises_res.data}
        ex_ids = list(ex_map.keys())
        
        # 3. Fetch logs for these exercise instances.
        logs_res = supabase.table("session_logs") \
            .select("session_exercise_id, actual_weight") \
            .in_("session_exercise_id", ex_ids) \
            .execute()
            
        # 4. Group by Date to find the Maximum Weight lifted in each session.
        progress_data = {}
        for log in logs_res.data:
            s_ex_id = log["session_exercise_id"]
            weight = log.get("actual_weight") or 0.0
            
            completed_at = ex_map.get(s_ex_id)
            if not completed_at:
                continue
                
            if completed_at not in progress_data:
                progress_data[completed_at] = weight
            else:
                progress_data[completed_at] = max(progress_data[completed_at], weight)
                
        # 5. Format results for the frontend chart.
        result = []
        for date_str, max_w in progress_data.items():
            result.append(ExerciseProgressResponse(
                session_date=date_str,
                max_weight=max_w
            ))
            
        # Sort results chronologically by date.
        result.sort(key=lambda x: x.session_date)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch exercise progress: {str(e)}")

