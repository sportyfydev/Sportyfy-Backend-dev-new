"""
SportyFY - Training Sessions & Workout Tracking Feature

Purpose:
This module provides endpoints for scheduling, managing, and tracking individual 
workout sessions. It handles the instantiation of sessions from templates 
and the logging of actual performance data (sets, reps, weight).

Application Context:
Core feature module for the Dashboard (upcoming sessions) and the Active Workout 
tracking screen.

Data Flow:
User/Trainer -> feature_training_sessions.py -> public.training_sessions -> 
public.session_exercises -> public.session_logs
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
import re
import requests
import os
from datetime import timedelta



from dependencies import get_current_user
from database import get_supabase
from supabase import Client
from features.schemas_training import (
    TrainingSessionCreate, TrainingSessionResponse,
    TrainingSessionUpdate,
    SessionExerciseCreate, SessionExerciseResponse,
    SessionLogCreate, SessionLogResponse,
    SessionComplete, UpcomingSessionResponse
)
from datetime import date, datetime
from features.feature_kpis import update_kpis_from_session
from features.utils_hashing import generate_training_hash

router = APIRouter()

@router.post("/", response_model=TrainingSessionResponse)
def create_training_session(
    session_data: TrainingSessionCreate, 
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Schedule a new training session for the authenticated user.
    
    Args:
        session_data (TrainingSessionCreate): The details of the workout (date, time, etc).
        current_user (dict): The authenticated trainee.
        supabase (Client): Injected Supabase client.
        
    Returns:
        TrainingSessionResponse: The newly scheduled session.
        
    Side Effects:
        - Inserts a record into 'training_sessions'.
        - Self-created sessions are automatically set to 'accepted' status.
    """
    try:
        # Include all fields, but exclude non-column fields
        payload = session_data.model_dump(exclude={"title", "description", "exercises", "youtube_url", "youtube_urls"})
        
        # FIX: date object is not JSON serializable by the Supabase client
        if payload.get("scheduled_date"):
            if hasattr(payload["scheduled_date"], "isoformat"):
                payload["scheduled_date"] = payload["scheduled_date"].isoformat()
            
        payload["trainee_id"] = current_user.get("id")
        payload["status"] = "accepted"
        payload["assigned_by"] = session_data.assigned_by or current_user.get("id")
        
        # If title/description provided in TrainingSessionCreate, they take precedence or fallback to template
        if session_data.title: payload["title"] = session_data.title
        if session_data.description: payload["description"] = session_data.description
        if session_data.youtube_url: payload["image_url"] = _get_youtube_thumbnail(session_data.youtube_url)

        response = supabase.table("training_sessions").insert(payload).execute()
        if not response.data:
            raise Exception("Failed to insert session")
        
        session = response.data[0]
        session_id = session["id"]

        # Handle Exercise Creation
        exercises_to_insert = []
        
        # 1. If explicit exercises provided
        if session_data.exercises:
            for ex in session_data.exercises:
                row = ex.model_dump()
                row["session_id"] = session_id
                exercises_to_insert.append(row)
        
        # 2. If YouTube URL or multiple URLs are provided and NO exercises were given (Auto-create)
        youtube_links = session_data.youtube_urls or []
        if session_data.youtube_url and session_data.youtube_url not in youtube_links:
            youtube_links.insert(0, session_data.youtube_url)

        if youtube_links and not session_data.exercises:
            for idx, link in enumerate(youtube_links):
                video_data = _get_youtube_video_data(link)
                video_id = video_data["id"]
                ex_name = video_data.get("title") or f"YouTube Workout ({video_id})"
                duration_seconds = video_data.get("duration_seconds")
                
                # Check if this "YouTube" exercise already exists for this user
                ex_resp = supabase.table("exercises").select("id").eq("owner_id", current_user["id"]).eq("media_url", link).execute()
                
                if ex_resp.data:
                    exercise_id = ex_resp.data[0]["id"]
                else:
                    # Create a new exercise record
                    new_ex = {
                        "name": ex_name,
                        "media_url": link,
                        "image_url": video_data.get("thumbnail") or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                        "owner_id": current_user["id"],
                        "visibility": "private",
                        "sport": payload.get("sport", "Sonstiges")
                    }
                    if duration_seconds:
                        new_ex["default_duration_seconds"] = duration_seconds

                    new_ex_resp = supabase.table("exercises").insert(new_ex).execute()
                    exercise_id = new_ex_resp.data[0]["id"]

                exercises_to_insert.append({
                    "session_id": session_id,
                    "exercise_id": exercise_id,
                    "order_index": idx,
                    "target_sets": 1,
                    "target_duration_seconds": duration_seconds
                })

        if exercises_to_insert:
            supabase.table("session_exercises").insert(exercises_to_insert).execute()

        return session
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create training session: {str(e)}")

def _get_youtube_video_data(url: str) -> Dict[str, Any]:
    video_id = _extract_youtube_id(url)
    api_key = os.environ.get("YOUTUBE_API_KEY")
    
    data = {
        "id": video_id,
        "title": None,
        "description": None,
        "duration_seconds": None,
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    }
    
    if not api_key or video_id == "default":
        return data
        
    try:
        api_url = f"https://www.googleapis.com/youtube/v3/videos?id={video_id}&part=snippet,contentDetails&key={api_key}"
        resp = requests.get(api_url, timeout=5)
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            if items:
                snippet = items[0].get("snippet", {})
                content_details = items[0].get("contentDetails", {})
                
                data["title"] = snippet.get("title")
                data["description"] = snippet.get("description")
                data["thumbnail"] = snippet.get("thumbnails", {}).get("high", {}).get("url")
                
                # Parse ISO 8601 duration (e.g., PT10M30S)
                duration_str = content_details.get("duration")
                if duration_str:
                    data["duration_seconds"] = _parse_iso8601_duration(duration_str)
    except Exception as e:
        print(f"Error fetching YouTube data: {e}")
        
    return data

def _parse_iso8601_duration(duration: str) -> int:
    # A simple parser for PT#H#M#S
    import re
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, duration)
    if not match:
        return 0
    
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    
    return hours * 3600 + minutes * 60 + seconds

def _extract_youtube_id(url: str) -> str:
    pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    return match.group(1) if match else "default"

def _get_youtube_thumbnail(url: str) -> str:
    video_id = _extract_youtube_id(url)
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


@router.get("/youtube-metadata")
def get_youtube_metadata(url: str, current_user: dict = Depends(get_current_user)):
    """Utility endpoint to fetch video metadata for the frontend editor."""
    return _get_youtube_video_data(url)


@router.get("/upcoming", response_model=List[UpcomingSessionResponse])
def get_upcoming_sessions(
    limit: int = 3, 
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Fetch the next upcoming accepted or pending training sessions for the Dashboard.
    
    Args:
        limit (int): Maximum number of sessions to return (default: 3).
        current_user (dict): The authenticated user.
        supabase (Client): Injected Supabase client.
        
    Returns:
        List[UpcomingSessionResponse]: A list of enriched session objects.
        
    Side Effects:
        - Performs a database query joining 'training_sessions' and 'training_templates'.
    """
    try:
        today = date.today().isoformat()

        # Fetch session metadata and join with template/trainer info.
        response = supabase.table("training_sessions") \
            .select("*, template:training_templates(title, description, sport, difficulty, image_url), trainer:users!assigned_by(first_name, last_name, email, username)") \
            .eq("trainee_id", current_user.get("id")) \
            .in_("status", ["accepted", "pending"]) \
            .gte("scheduled_date", today) \
            .order("scheduled_date") \
            .limit(limit) \
            .execute()

        # Build response with template title fallback if a template is attached.
        upcoming = []
        for s in response.data:
            template_data = s.pop("template", None)
            # Handle potential list response from Supabase join
            if isinstance(template_data, list) and template_data:
                template_data = template_data[0]
            elif not template_data:
                template_data = {}
                
            upcoming.append({
                **s,
                "title": template_data.get("title") or s.get("scheduled_date", "Training"),
                "description": template_data.get("description") or "",
                "sport": template_data.get("sport") or "Fitness",
                "difficulty": template_data.get("difficulty") or "Mittel",
                "is_trainer_assigned": s.get("assigned_by") is not None,
            })

        return upcoming
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch upcoming sessions: {str(e)}")

@router.post("/instantiate/{template_id}", response_model=TrainingSessionResponse)
def instantiate_session(
    template_id: str, 
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Create a new training session based on an existing template, deep-copying its exercises.
    
    Args:
        template_id (str): The ID of the template to instantiate.
        current_user (dict): The authenticated user.
        supabase (Client): Injected Supabase client.
        
    Returns:
        TrainingSessionResponse: The newly created session.
        
    Side Effects:
        - Inserts into 'training_sessions'.
        - Inserts multiple records into 'session_exercises'.
    """
    try:
        # 1. Fetch template to ensure it exists and we have a reference.
        template = supabase.table("training_templates").select("id").eq("id", template_id).single().execute()
        if not template.data:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # 2. Create the session header, copying title, description and image_url from template if available
        # But wait, TrainingSessionCreate has these fields optional. If they are provided, use them.
        # Otherwise, we might want to copy from template later or have it as fallback in the UI.
        # Let's check the template more broadly.
        template_full = supabase.table("training_templates").select("*").eq("id", template_id).single().execute()
        t_data = template_full.data or {}

        session_payload = {
            "trainee_id": current_user.get("id"),
            "template_id": template_id,
            "status": "pending",
            "scheduled_date": datetime.now().date().isoformat(),
            "title": t_data.get("title"),
            "description": t_data.get("description"),
            "image_url": t_data.get("image_url"),
            "assigned_by": t_data.get("owner_id") or current_user.get("id")
        }
        
        session_res = supabase.table("training_sessions").insert(session_payload).execute()
        if not session_res.data:
            raise Exception("Failed to insert session")
            
        session = session_res.data[0]
        session_id = session["id"]
        
        # 3. Fetch template exercises to copy them as snapshots for this session.
        exercises = supabase.table("template_exercises").select("*").eq("template_id", template_id).execute()
        
        # 4. Copy each exercise, stripping template-specific metadata.
        if exercises.data:
            session_exercises_payload = []
            for ex in exercises.data:
                ex_copy = dict(ex)
                ex_copy.pop("id", None) # Remove template exercise UUID
                ex_copy.pop("template_id", None)
                ex_copy.pop("created_at", None)
                ex_copy["session_id"] = session_id
                session_exercises_payload.append(ex_copy)
                
            supabase.table("session_exercises").insert(session_exercises_payload).execute()
        
        return session
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to instantiate session: {str(e)}")

@router.get("/", response_model=List[TrainingSessionResponse])
def list_training_sessions(
    include_exercises: bool = False,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Retrieve all training sessions assigned to or created by the currently authenticated user.
    
    Args:
        include_exercises (bool): Whether to include full exercise details and content hash.
        current_user (dict): The authenticated user.
        supabase (Client): Injected Supabase client.
        
    Returns:
        List[TrainingSessionResponse]: Historical and scheduled sessions.
    """
    try:
        from database import retry_supabase_operation
        # Optimization: Only select exercises if requested
        select_string = "*, template:training_templates(title, description, sport, difficulty, image_url), trainer:users!assigned_by(first_name, last_name, email, username)"
        if include_exercises:
            select_string += ", exercises:session_exercises(*)"

        response = retry_supabase_operation(
            lambda: supabase.table("training_sessions") \
                .select(select_string) \
                .eq("trainee_id", current_user.get("id")) \
                .order("scheduled_date", desc=True) \
                .execute()
        )
        
        sessions = []
        for s in response.data:
            template_data = s.pop("template", None)
            if isinstance(template_data, list) and template_data:
                template_data = template_data[0]
            elif not template_data:
                template_data = {}

            item = {
                **s,
                "title": template_data.get("title") or s.get("title") or s.get("scheduled_date", "Training"),
                "description": template_data.get("description") or s.get("description") or "",
                "sport": template_data.get("sport") or "Fitness",
                "difficulty": template_data.get("difficulty") or "Mittel",
                "is_trainer_assigned": s.get("assigned_by") is not None,
            }

            if include_exercises:
                exs = s.get("exercises", [])
                item["exercises"] = exs
                item["content_hash"] = generate_training_hash(item["title"], item["description"], exs)

            sessions.append(item)
            
        return sessions
    except Exception as e:
        import traceback
        logging.error(f"Error in list_training_sessions: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch training sessions: {str(e)}")

@router.get("/{session_id}")
def get_training_session(
    session_id: str, 
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Retrieve full details of a specific session, including its exercises.
    
    Args:
        session_id (str): The UUID of the session.
        current_user (dict): The authenticated user.
        supabase (Client): Injected Supabase client.
        
    Returns:
        dict: Session details with an 'exercises' list attached.
        
    Raises:
        HTTPException: 404 if not found, 403 if user doesn't own the session.
    """
    try:
        # Verify access and fetch basic session data.
        session = supabase.table("training_sessions") \
            .select("*, template:training_templates(title, description, sport, difficulty, image_url), trainer:users!assigned_by(first_name, last_name, email, username)") \
            .eq("id", session_id) \
            .single() \
            .execute()
        if not session.data:
            raise HTTPException(status_code=404, detail="Session not found")
            
        if session.data.get("trainee_id") != current_user.get("id"):
            raise HTTPException(status_code=403, detail="Not authorized to view this session")
            
        # Fetch associated session exercises to provide a full rich response for the tracking UI.
        exercises = supabase.table("session_exercises").select("*").eq("session_id", session_id).order("order_index").execute()
        
        result = session.data
        result["exercises"] = exercises.data
        
        # Add hash
        template_meta = result.get("template") or {}
        if isinstance(template_meta, list) and template_meta: template_meta = template_meta[0]
        result["content_hash"] = generate_training_hash(template_meta.get("title") or result.get("title"), template_meta.get("description") or result.get("description"), exercises.data)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch training session: {str(e)}")

@router.patch("/{session_id}", response_model=TrainingSessionResponse)
def update_training_session(
    session_id: str,
    update_data: TrainingSessionUpdate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Partially update an existing training session.

    Args:
        session_id (str): The UUID of the session to update.
        update_data (TrainingSessionUpdate): Fields to patch.
        current_user (dict): The authenticated user.
        supabase (Client): Injected Supabase client.

    Returns:
        TrainingSessionResponse: The updated session.

    Side Effects:
        - Updates 'training_sessions' row.
        - If sport/difficulty provided, also updates the linked template.
    """
    try:
        # Verify ownership
        session_resp = supabase.table("training_sessions").select("trainee_id, template_id").eq("id", session_id).single().execute()
        if not session_resp.data or session_resp.data.get("trainee_id") != current_user.get("id"):
            raise HTTPException(status_code=403, detail="Not authorized to modify this session")

        # Build patch dict for training_sessions
        session_patch = {}
        if update_data.scheduled_date is not None:
            session_patch["scheduled_date"] = update_data.scheduled_date.isoformat()
        if update_data.scheduled_time is not None:
            session_patch["scheduled_time"] = update_data.scheduled_time
        if update_data.image_url is not None:
            session_patch["image_url"] = update_data.image_url

        if session_patch:
            resp = supabase.table("training_sessions").update(session_patch).eq("id", session_id).execute()
            if not resp.data:
                raise Exception("Failed to update session")

        # Update title, description, sport and difficulty on the linked template
        template_patch = {}
        if update_data.title is not None:
            template_patch["title"] = update_data.title
        if update_data.description is not None:
            template_patch["description"] = update_data.description
        if update_data.sport is not None:
            template_patch["sport"] = update_data.sport
        if update_data.difficulty is not None:
            template_patch["difficulty"] = update_data.difficulty

        template_id = session_resp.data.get("template_id")
        if template_patch and template_id:
            supabase.table("training_templates").update(template_patch).eq("id", template_id).execute()

        # Return full updated session
        updated = supabase.table("training_sessions").select("*").eq("id", session_id).single().execute()
        return updated.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update session: {str(e)}")

@router.put("/{session_id}/exercises", response_model=List[SessionExerciseResponse])
def replace_session_exercises(
    session_id: str,
    exercises: List[SessionExerciseCreate],
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Replace all exercises of a session (delete existing, insert new list).

    Args:
        session_id (str): Target session.
        exercises (List[SessionExerciseCreate]): Complete new exercise list.
        current_user (dict): Authenticated user.
        supabase (Client): Injected Supabase client.

    Returns:
        List[SessionExerciseResponse]: The newly inserted exercises.

    Side Effects:
        - Deletes all existing 'session_exercises' for this session.
        - Inserts the provided list.
    """
    try:
        # Verify ownership
        session_resp = supabase.table("training_sessions").select("trainee_id").eq("id", session_id).single().execute()
        if not session_resp.data or session_resp.data.get("trainee_id") != current_user.get("id"):
            raise HTTPException(status_code=403, detail="Not authorized to modify this session")

        # Delete existing exercises
        supabase.table("session_exercises").delete().eq("session_id", session_id).execute()

        # Insert new exercises
        if not exercises:
            return []

        rows_to_insert = []
        for ex in exercises:
            row = ex.model_dump()
            row["session_id"] = session_id
            rows_to_insert.append(row)

        resp = supabase.table("session_exercises").insert(rows_to_insert).execute()
        return resp.data or []
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error replacing exercises for session {session_id}: {str(e)}")
        print(f"Rows to insert: {rows_to_insert}")
        raise HTTPException(status_code=500, detail=f"Failed to replace exercises: {str(e)}")


@router.post("/{session_id}/exercises", response_model=SessionExerciseResponse)
def add_session_exercise(
    session_id: str, 
    exercise_data: SessionExerciseCreate, 
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Add a manual exercise entry to an existing session.
    
    Args:
        session_id (str): Target session.
        exercise_data (SessionExerciseCreate): Exercise targets.
        current_user (dict): Authenticated user.
        supabase (Client): Injected Supabase client.
        
    Returns:
        SessionExerciseResponse: The created exercise snapshot.
    """
    try:
        # Verify ownership before allowing modifications.
        session = supabase.table("training_sessions").select("trainee_id").eq("id", session_id).single().execute()
        if not session.data or session.data.get("trainee_id") != current_user.get("id"):
            raise HTTPException(status_code=403, detail="Not authorized to modify this session")
            
        data_to_insert = exercise_data.model_dump()
        data_to_insert["session_id"] = session_id
        response = supabase.table("session_exercises").insert(data_to_insert).execute()
        if not response.data:
            raise Exception("Failed to insert session exercise")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add exercise: {str(e)}")

@router.post("/exercises/{session_exercise_id}/logs", response_model=SessionLogResponse)
def log_exercise_set(
    session_exercise_id: str, 
    log_data: SessionLogCreate, 
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Log actual performance for a completed set of an exercise.
    
    Args:
        session_exercise_id (str): The specific exercise snapshot to log against.
        log_data (SessionLogCreate): Actual reps, weight, and duration.
        current_user (dict): Authenticated user.
        supabase (Client): Injected Supabase client.
        
    Returns:
        SessionLogResponse: The logged set record.
        
    Side Effects:
        - Inserts into 'session_logs'.
    """
    try:
        # Security: Verify that the session_exercise_id belongs to a session owned by the current user.
        # This is critical because we use a service role that bypasses RLS.
        check_query = supabase.table("session_exercises") \
            .select("id, training_sessions!inner(trainee_id)") \
            .eq("id", session_exercise_id) \
            .single() \
            .execute()
            
        if not check_query.data:
            raise HTTPException(status_code=404, detail="Session exercise not found")
            
        # Access nested join data: training_sessions is a dict because of .single()
        trainee_id = check_query.data.get("training_sessions", {}).get("trainee_id")
        if trainee_id != current_user.get("id"):
             raise HTTPException(status_code=403, detail="Not authorized to log for this exercise")

        data_to_insert = log_data.model_dump()
        data_to_insert["session_exercise_id"] = session_exercise_id
        response = supabase.table("session_logs").insert(data_to_insert).execute()
        if not response.data:
            raise Exception("Failed to insert session log")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log set: {str(e)}")

@router.patch("/{session_id}/complete")
def complete_session(
    session_id: str, 
    complete_data: SessionComplete, 
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Mark a training session as finished, logging user feedback.
    
    Args:
        session_id (str): The session to close.
        complete_data (SessionComplete): RPE score from 1 to 10.
        current_user (dict): Authenticated user.
        supabase (Client): Injected Supabase client.
        
    Returns:
        dict: Confirmation message and updated session data.
        
    Side Effects:
        - Updates 'training_sessions' status to 'completed'.
    """
    try:
        # Verify access and ownership.
        session = supabase.table("training_sessions").select("trainee_id").eq("id", session_id).single().execute()
        if not session.data or session.data.get("trainee_id") != current_user.get("id"):
            raise HTTPException(status_code=403, detail="Not authorized to modify this session")
            
        # Update the session status and store the RPE feedback score.
        update_payload = {
            "status": "completed",
            "feedback_rpe": complete_data.feedback_rpe,
            "completed_at": datetime.now().isoformat()
        }
        response = supabase.table("training_sessions").update(update_payload).eq("id", session_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Session not found or not updated")
            
        # Trigger KPI Update (Phase 2 Automation)
        update_kpis_from_session(session_id, supabase)
        
        return {"message": "Session marked as completed", "data": response.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete session: {str(e)}")
