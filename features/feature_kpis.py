"""
SportyFY - KPI Tracking Feature

Purpose:
This module provides endpoints for managing KPI definitions, targets, 
and measurements. It handles the core logic for performance tracking.

Data Flow:
User -> feature_kpis.py -> Supabase DB (KPI tables)
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from dependencies import get_current_user
from database import get_supabase
from supabase import Client
from features.schemas_kpis import (
    KPIDefinitionCreate, KPIDefinitionResponse,
    KPITargetCreate, KPITargetResponse,
    KPIMeasurementCreate, KPIMeasurementResponse,
    KPIDashboardItem
)

router = APIRouter()

# --- KPI Definitions ---

@router.get("/definitions", response_model=List[KPIDefinitionResponse])
def list_kpi_definitions(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """List available KPI definitions (platform + own)."""
    try:
        res = supabase.table("kpi_definitions").select("*") \
            .or_(f"user_id.is.null,user_id.eq.{current_user['id']}") \
            .execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch KPI definitions: {str(e)}")

@router.post("/definitions", response_model=KPIDefinitionResponse)
def create_kpi_definition(
    data: KPIDefinitionCreate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Create a user-specific KPI definition."""
    try:
        insert_data = data.model_dump()
        insert_data["user_id"] = current_user["id"]
        res = supabase.table("kpi_definitions").insert(insert_data).execute()
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create KPI definition: {str(e)}")

@router.delete("/definitions/{kpi_id}")
def delete_kpi_definition(
    kpi_id: UUID,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Deletes a custom KPI definition along with its targets and measurements."""
    try:
        # 1. Fetch to check ownership and platform status
        res = supabase.table("kpi_definitions").select("*").eq("id", str(kpi_id)).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="KPI Definition nicht gefunden")
        
        definition = res.data
        if definition.get("is_platform"):
            raise HTTPException(status_code=403, detail="Standard-KPIs können nicht gelöscht werden")
        
        if definition.get("user_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Keine Berechtigung zum Löschen dieses KPIs")

        # 2. Sequential deletion (cascading)
        # Delete measurements first
        supabase.table("kpi_measurements").delete().eq("kpi_id", str(kpi_id)).execute()
        # Delete target
        supabase.table("kpi_targets").delete().eq("kpi_id", str(kpi_id)).execute()
        # Delete the definition itself
        supabase.table("kpi_definitions").delete().eq("id", str(kpi_id)).execute()
        
        return {"status": "success", "message": "KPI wurde erfolgreich gelöscht"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Löschen: {str(e)}")

# --- KPI Targets ---

@router.get("/targets", response_model=List[KPITargetResponse])
def list_kpi_targets(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """List current user's KPI targets."""
    try:
        res = supabase.table("kpi_targets").select("*") \
            .eq("user_id", current_user["id"]) \
            .execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch KPI targets: {str(e)}")

@router.post("/targets", response_model=KPITargetResponse)
def create_kpi_target(
    data: KPITargetCreate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Set or update a KPI target."""
    try:
        # Use mode='json' to ensure UUIDs and dates are strings
        insert_data = data.model_dump(mode='json')
        insert_data["user_id"] = current_user["id"]
        
        # Check if target for this KPI already exists? 
        # For simplicity, we just insert.
        res = supabase.table("kpi_targets").insert(insert_data).execute()
        
        if not res.data:
            raise Exception("No data returned from insert")
            
        return res.data[0]
    except Exception as e:
        print(f"DEBUG: create_kpi_target error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set KPI target: {str(e)}")

@router.patch("/targets/{target_id}", response_model=KPITargetResponse)
def update_kpi_target(
    target_id: UUID,
    data: dict, # Support partial updates
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Update an existing KPI target (e.g. pin status or value)."""
    try:
        # Verify ownership
        check = supabase.table("kpi_targets").select("user_id").eq("id", str(target_id)).single().execute()
        if not check.data or check.data["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized")

        # If pinning, we might want to ensure only 3 are pinned?
        # Let's check pinned count if data has is_pinned=True
        if data.get("is_pinned") is True:
            pinned_res = supabase.table("kpi_targets") \
                .select("id", count="exact") \
                .eq("user_id", current_user["id"]) \
                .eq("is_pinned", True) \
                .execute()
            if pinned_res.count and pinned_res.count >= 3:
                raise HTTPException(status_code=400, detail="Maximum 3 KPIs können angepinnt werden.")

        res = supabase.table("kpi_targets").update(data).eq("id", str(target_id)).execute()
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: update_kpi_target error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update target: {str(e)}")

# --- KPI Measurements ---

@router.post("/measurements", response_model=KPIMeasurementResponse)
def log_kpi_measurement(
    data: KPIMeasurementCreate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Log a new measurement for a KPI."""
    try:
        insert_data = data.model_dump(mode='json')
        insert_data["user_id"] = current_user["id"]
             
        res = supabase.table("kpi_measurements").insert(insert_data).execute()
        return res.data[0]
    except Exception as e:
        print(f"DEBUG: log_kpi_measurement error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to log measurement: {str(e)}")

@router.post("/sync")
def sync_user_kpis(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Manually triggers a full recalculation of all automatic KPIs for the user."""
    try:
        user_id = current_user["id"]
        
        # 1. Identify all automatic KPI IDs for this user
        kpi_defs = supabase.table("kpi_definitions") \
            .select("id") \
            .eq("source_type", "automatic_training") \
            .execute()
        
        auto_kpi_ids = [k["id"] for k in kpi_defs.data] if kpi_defs.data else []
        
        if not auto_kpi_ids:
            return {"status": "success", "message": "Keine automatischen KPIs zum Synchronisieren gefunden."}

        # 2. Clear existing automatic measurements for these KPIs
        # We only delete measurements for the KPIs that are marked as automatic
        supabase.table("kpi_measurements") \
            .delete() \
            .eq("user_id", user_id) \
            .in_("kpi_id", auto_kpi_ids) \
            .execute()

        # 3. Fetch all completed training sessions for this user
        sessions = supabase.table("training_sessions") \
            .select("id") \
            .eq("trainee_id", user_id) \
            .eq("status", "completed") \
            .order("completed_at", desc=False) \
            .execute()

        if not sessions.data:
            return {"status": "success", "message": "Keine Trainings-Daten zum Synchronisieren gefunden."}

        # 4. Re-calculate for each session
        for session in sessions.data:
            update_kpis_from_session(session["id"], supabase)

        return {"status": "success", "message": "KPIs erfolgreich neu berechnet."}
    except Exception as e:
        print(f"DEBUG: sync_user_kpis error: {e}")
        raise HTTPException(status_code=500, detail=f"Synchronisierung fehlgeschlagen: {str(e)}")

# --- KPI Automation ---

def update_kpis_from_session(session_id: str, supabase: Client):
    """
    Analyzes a completed training session and logs relevant KPI measurements.
    
    Triggered by: complete_session in feature_training_sessions.py
    """
    try:
        # 1. Fetch user_id and session data
        session_res = supabase.table("training_sessions") \
            .select("trainee_id, completed_at") \
            .eq("id", session_id).single().execute()
        
        if not session_res.data:
            print(f"KPI Sync: Session {session_id} not found.")
            return
            
        user_id = session_res.data["trainee_id"]
        measured_at = session_res.data["completed_at"] or datetime.now().isoformat()

        # 2. Fetch exercises and sets
        # session_exercises -> session_logs
        exercises_res = supabase.table("session_exercises") \
            .select("id, exercise_id, logs:session_logs(*)") \
            .eq("session_id", session_id).execute()
        
        exercises = exercises_res.data or []
        
        # 3. Calculate metrics
        total_volume = 0.0
        exercise_maxes = {} # exercise_id -> max_weight
        
        for ex in exercises:
            ex_id = ex.get("exercise_id")
            for log in ex.get("logs", []):
                reps = log.get("actual_reps") or 0
                weight = float(log.get("actual_weight") or 0.0)
                total_volume += reps * weight
                
                if ex_id:
                    exercise_maxes[ex_id] = max(exercise_maxes.get(ex_id, 0.0), weight)

        # 4. Find valid KPI targets for this user (automatic or linked)
        targets_res = supabase.table("kpi_targets") \
            .select("*, kpi:kpi_definitions(*)") \
            .eq("user_id", user_id).execute()
        
        targets = targets_res.data or []
        new_measurements = []

        for t in targets:
            kpi = t["kpi"]
            source = kpi.get("source_type")
            category = kpi.get("category")
            
            # Case A: Trainingsvolumen (automatic_training)
            if source == "automatic_training" and category == "training_volume":
                new_measurements.append({
                    "user_id": user_id,
                    "kpi_id": kpi["id"],
                    "measured_value": total_volume,
                    "measured_at": measured_at,
                    "source_reference": {"session_id": session_id}
                })
            
            # Case B: Trainingsfrequenz (consistency)
            elif source == "automatic_training" and category == "consistency":
                new_measurements.append({
                    "user_id": user_id,
                    "kpi_id": kpi["id"],
                    "measured_value": 1.0, # +1 session
                    "measured_at": measured_at,
                    "source_reference": {"session_id": session_id}
                })
            
            # Case C: Linked Exercises (PRs)
            elif source == "exercise_linked":
                linked_ex_id = kpi.get("linked_exercise_id")
                if linked_ex_id in exercise_maxes:
                    new_measurements.append({
                        "user_id": user_id,
                        "kpi_id": kpi["id"],
                        "measured_value": exercise_maxes[linked_ex_id],
                        "measured_at": measured_at,
                        "source_reference": {"session_id": session_id}
                    })

        # 5. Insert measurements in bulk
        if new_measurements:
            supabase.table("kpi_measurements").insert(new_measurements).execute()
            print(f"KPI Sync: Logged {len(new_measurements)} measurements for session {session_id}")

    except Exception as e:
        print(f"KPI Sync Error: {str(e)}")

# --- KPI Dashboard ---

@router.get("/dashboard", response_model=List[KPIDashboardItem])
def get_kpi_dashboard(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Get aggregated KPI dashboard data for the user.
    Calculates current progress and trends.
    """
    try:
        from database import retry_supabase_operation
        # 1. Fetch active targets
        targets_res = retry_supabase_operation(
            lambda: supabase.table("kpi_targets") \
                .select("*, kpi:kpi_definitions(*)") \
                .eq("user_id", current_user["id"]) \
                .execute()
        )
        
        dashboard_items = []
        
        for t in targets_res.data:
            kpi_def = t.get("kpi")
            if not kpi_def:
                print(f"DEBUG: Skipping target {t.get('id')} because kpi_definition is missing.")
                continue
                
            kpi_id = t["kpi_id"]
            
            # 2. Fetch recent measurements (no longer filtered by start_date at DB level to allow charts)
            measurements_res = retry_supabase_operation(
                lambda: supabase.table("kpi_measurements") \
                    .select("*") \
                    .eq("user_id", current_user["id"]) \
                    .eq("kpi_id", kpi_id) \
                    .order("measured_at", desc=True) \
                    .limit(30) \
                    .execute()
            )
            
            all_measurements = measurements_res.data
            
            # 3. Calculate current value based on tracking_type
            current_val = 0.0
            if all_measurements:
                if kpi_def["tracking_type"] == "latest_value":
                    # Use the absolute latest measurement available
                    current_val = float(all_measurements[0]["measured_value"])
                elif kpi_def["tracking_type"] == "max_value":
                    # Use all-time maximum
                    current_val = max(float(m["measured_value"]) for m in all_measurements)
                elif kpi_def["tracking_type"] == "cumulative":
                    # Only sum measurements SINCE the target's start_date
                    since_date = t["start_date"]
                    filtered = [m for m in all_measurements if m["measured_at"] >= since_date]
                    current_val = sum(float(m["measured_value"]) for m in filtered)
                elif kpi_def["tracking_type"] == "min_value":
                    # Use all-time minimum
                    current_val = min(float(m["measured_value"]) for m in all_measurements)
            
            # 4. Progress percentage
            target_val = float(t["target_value"])
            progress = (current_val / target_val * 100) if target_val > 0 else 0
            
            # 5. Trend (very simple for now: compare latest with one before)
            trend = "stable"
            if len(all_measurements) >= 2:
                latest = float(all_measurements[0]["measured_value"])
                previous = float(all_measurements[1]["measured_value"])
                if latest > previous: trend = "up"
                elif latest < previous: trend = "down"
            
            dashboard_items.append({
                "kpi_id": kpi_id,
                "name": kpi_def["name"],
                "category": kpi_def["category"],
                "unit": kpi_def["unit"],
                "visualization": kpi_def.get("visualization", "line"),
                "target": t,
                "current_value": current_val,
                "progress_percentage": min(progress, 100.0),
                "trend_direction": trend,
                "history": all_measurements
            })
            
        return dashboard_items
    except Exception as e:
        import traceback
        logging.error(f"Error in get_kpi_dashboard: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate KPI dashboard: {str(e)}")

@router.delete("/measurements/{measurement_id}")
def delete_kpi_measurement(
    measurement_id: UUID,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Delete a KPI measurement (cleanup)."""
    try:
        # Verify ownership
        check = supabase.table("kpi_measurements").select("user_id").eq("id", str(measurement_id)).single().execute()
        if not check.data or check.data["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        supabase.table("kpi_measurements").delete().eq("id", str(measurement_id)).execute()
        return {"message": "Measurement deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete measurement: {str(e)}")
