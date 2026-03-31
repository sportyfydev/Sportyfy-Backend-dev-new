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
from datetime import datetime, timedelta, date
import logging
import traceback

from dependencies import get_current_user
from database import get_supabase
from supabase import Client
from features.schemas_kpis import (
    KPIDefinitionCreate, KPIDefinitionResponse,
    KPITargetCreate, KPITargetResponse,
    KPIMeasurementCreate, KPIMeasurementResponse,
    KPIDashboardItem, KPIPreviewRequest, KPIPreviewResponse
)

router = APIRouter()

# --- Helpers ---

def get_cycle_bounds(period: str, ref_date: datetime = None):
    """
    Zweck: Berechnet die Start- und End-Zeitstempel für einen gegebenen Zeitraum (daily, weekly, monthly, yearly).
    Parameter:
        - period: Der Zeit-Zyklus.
        - ref_date: Referenz-Datum (Standard: jetzt).
    Return-Wert: (start_datetime, end_datetime).
    Side-Effects: Keine.
    """
    import calendar
    if not ref_date: ref_date = datetime.now()
    
    if period == "daily":
        start = ref_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)
    elif period == "weekly":
        # Monday start (ISO)
        start = ref_date - timedelta(days=ref_date.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=7)
    elif period == "monthly":
        start = ref_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_day = calendar.monthrange(start.year, start.month)[1]
        end = start.replace(day=end_day, hour=23, minute=59, second=59)
        return start, end
    elif period == "yearly":
        start = ref_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = ref_date.replace(month=12, day=31, hour=23, minute=59, second=59)
        return start, end
    return None, None

# --- KPI Definitions ---

@router.get("/definitions", response_model=List[KPIDefinitionResponse])
def list_kpi_definitions(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Zweck: Listet alle verfügbaren KPI-Definitionen (System-Vorgaben + eigene) auf.
    Parameter:
        - current_user: Der aktuell authentifizierte Benutzer.
        - supabase: Der Datenbank-Client.
    Return-Wert: Liste von KPI-Definitionen.
    Side-Effects: Keine.
    """
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
    """
    Zweck: Erstellt eine neue benutzerdefinierte KPI-Definition.
    Parameter:
        - data: Die Daten für die neue Definition (Name, Einheit, etc.).
        - current_user: Der Ersteller der Definition.
        - supabase: Der Datenbank-Client.
    Return-Wert: Die erstellte KPI-Definition.
    Side-Effects: Erstellt einen Eintrag in der Tabelle 'kpi_definitions'.
    """
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
    """
    Zweck: Löscht eine eigene KPI-Definition samt zugehöriger Ziele und Messwerte.
    Parameter:
        - kpi_id: Die ID der zu löschenden Definition.
        - current_user: Der anfragende Benutzer (muss Eigentümer sein).
        - supabase: Der Datenbank-Client.
    Return-Wert: Erfolgsmeldung.
    Side-Effects: Löscht Einträge in 'kpi_measurements', 'kpi_targets' und 'kpi_definitions'.
    """
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
    """
    Zweck: Listet alle KPI-Ziele (Dashboard-Karten) des Benutzers auf.
    Parameter:
        - current_user: Der Eigentümer der Ziele.
        - supabase: Der Datenbank-Client.
    Return-Wert: Liste von KPI-Zielen.
    Side-Effects: Keine.
    """
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
    """
    Zweck: Erstellt ein neues KPI-Ziel (eine Visualisierungskarte auf dem Dashboard).
    Parameter:
        - data: Konfiguration des Ziels (KPI-ID, Zielwert, Modus, etc.).
        - current_user: Der Ersteller des Ziels.
        - supabase: Der Datenbank-Client.
    Return-Wert: Das erstellte KPI-Ziel.
    Side-Effects: Erstellt einen Eintrag in der Tabelle 'kpi_targets'.
    """
    try:
        user_id = current_user["id"]
        kpi_id = str(data.kpi_id)
        
        # For multi-visualization support, we only update if a specific 'id' is passed 
        # or if we want to enforce ONE target per (user, kpi, visualization) combination.
        # For now, let's allow multiple. The user handles deletion.
        
        insert_data = data.model_dump(mode='json')
        insert_data["user_id"] = user_id
        
        # INSERT new target every time to allow multi-visualization
        # (The user can delete unwanted ones in the UI)
        res = supabase.table("kpi_targets").insert(insert_data).execute()
        
        if not res.data:
            raise Exception("No data returned from operation")
            
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
    """
    Zweck: Aktualisiert die Konfiguration eines bestehenden KPI-Ziels.
    Parameter:
        - target_id: Die ID des zu aktualisierenden Ziels.
        - data: Die zu ändernden Felder (z. B. Zielwert oder Pin-Status).
        - current_user: Der Eigentümer des Ziels.
        - supabase: Der Datenbank-Client.
    Return-Wert: Das aktualisierte KPI-Ziel.
    Side-Effects: Modifiziert einen Eintrag in der Tabelle 'kpi_targets'.
    """
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

@router.delete("/targets/{target_id}")
def delete_kpi_target(
    target_id: UUID,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Zweck: Löscht ein spezifisches KPI-Ziel (Dashboard-Karte).
    Parameter:
        - target_id: Die ID des zu löschenden Ziels.
        - current_user: Der Eigentümer des Ziels.
        - supabase: Der Datenbank-Client.
    Return-Wert: Erfolgsmeldung.
    Side-Effects: 
        - Löscht Eintrag in 'kpi_targets'.
        - Löscht 'kpi_definitions' und 'kpi_measurements', falls dies die letzte Verknüpfung für eine eigene KPI war.
    """
    try:
        # 1. Fetch target to get kpi_id and confirm ownership
        target_res = supabase.table("kpi_targets").select("*, kpi:kpi_definitions(*)").eq("id", str(target_id)).single().execute()
        if not target_res.data:
            raise HTTPException(status_code=404, detail="KPI Target nicht gefunden")
            
        target = target_res.data
        if target["user_id"] != current_user["id"]:
             raise HTTPException(status_code=403, detail="Keine Berechtigung")

        kpi_id = target["kpi_id"]
        kpi_def = target.get("kpi")

        # 2. Delete the target
        supabase.table("kpi_targets").delete().eq("id", str(target_id)).execute()

        # 3. Check if any other targets exist for this KPI and user
        other_targets = supabase.table("kpi_targets").select("id", count="exact") \
            .eq("user_id", current_user["id"]) \
            .eq("kpi_id", kpi_id) \
            .execute()
            
        # other_targets.count returns the total count if requested
        if not other_targets.data or len(other_targets.data) == 0:
            # No more targets using this KPI definition for this user
            # If it's a custom KPI (not platform), we should clean up definition and measurements
            if kpi_def and not kpi_def.get("is_platform") and kpi_def.get("user_id") == current_user["id"]:
                # Delete measurements
                supabase.table("kpi_measurements").delete().eq("user_id", current_user["id"]).eq("kpi_id", kpi_id).execute()
                # Delete definition
                supabase.table("kpi_definitions").delete().eq("id", kpi_id).execute()
                return {"status": "success", "message": "KPI Card und Definition erfolgreich gelöscht"}
        
        return {"status": "success", "message": "KPI Card erfolgreich entfernt"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: delete_kpi_target error: {e}")
        raise HTTPException(status_code=500, detail=f"Fehler beim Löschen: {str(e)}")

# --- KPI Measurements ---

@router.post("/measurements", response_model=KPIMeasurementResponse)
def log_kpi_measurement(
    data: KPIMeasurementCreate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Zweck: Loggt einen neuen Messwert für eine KPI (manuelle Eingabe).
    Parameter:
        - data: Messwert, Zeitstempel und KPI-ID.
        - current_user: Der Benutzer, der den Wert loggt.
        - supabase: Der Datenbank-Client.
    Return-Wert: Der erstellte Messwert-Eintrag.
    Side-Effects: Erstellt einen Eintrag in 'kpi_measurements'.
    """
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
    """
    Zweck: Triggert eine vollständige Neuberechnung aller automatischen KPIs basierend auf dem Trainingsverlauf.
    Parameter:
        - current_user: Der Benutzer, dessen KPIs synchronisiert werden sollen.
        - supabase: Der Datenbank-Client.
    Return-Wert: Erfolgsmeldung.
    Side-Effects: 
        - Löscht bestehende automatische Messwerte des Benutzers.
        - Scannt alle abgeschlossenen Trainings und erstellt neue Messwerte.
    """
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
    Zweck: Analysiert eine abgeschlossene Trainingseinheit und extrahiert KPI-relevante Daten (Volumen, PRs etc.).
    Parameter:
        - session_id: Die ID der soeben abgeschlossenen Session.
        - supabase: Der Datenbank-Client.
    Return-Wert: Keiner.
    Side-Effects: Erstellt Einträge in 'kpi_measurements' für alle betroffenen KPIs.
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

# --- Dynamic KPI Engine ---

import uuid

def evaluate_dynamic_kpi(user_id: str, kpi_id: str, query_config: dict, supabase: Client) -> List[dict]:
    """
    Zweck: Berechnet Messwerte "on-the-fly" basierend auf einer dynamischen Abfrage-Konfiguration (query_config).
    Parameter:
        - user_id: ID des Benutzers.
        - kpi_id: ID der KPI-Definition.
        - query_config: JSON-Konfiguration (Entity, Field, Filter).
        - supabase: Der Datenbank-Client.
    Return-Wert: Liste von simulierten Messwert-Objekten.
    Side-Effects: Keine persistenten Änderungen (Read-Only Scan der Trainingsdaten).
    """
    entity = query_config.get("entity")
    field = query_config.get("field")
    filters = query_config.get("filters") or {}
    
    measurements = []
    
    try:
        if entity == "sessions":
            # Simple session query
            ts_data = supabase.table("training_sessions").select("id, completed_at, scheduled_date, status, template_id").eq("trainee_id", user_id).execute().data
            for s in ts_data:
                if filters.get("status") and s.get("status") != filters["status"]: continue
                if filters.get("template_id") and str(s.get("template_id")) != str(filters["template_id"]): continue
                
                date_str = s.get("completed_at") or s.get("scheduled_date")
                if not date_str: continue
                
                measurements.append({
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "kpi_id": kpi_id,
                    "measured_at": date_str,
                    "measured_value": 1.0,
                    "source_reference": {"session_id": s["id"]},
                    "created_at": date_str
                })
                
        elif entity == "logs":
            # Deep relational query
            ts_data = supabase.table("training_sessions").select(
                "id, completed_at, scheduled_date, status, template_id, session_exercises(id, exercise_id, session_logs(id, actual_reps, actual_weight, actual_duration_seconds))"
            ).eq("trainee_id", user_id).execute().data
            
            for s in ts_data:
                if filters.get("status") and s.get("status") != filters["status"]: continue
                if filters.get("template_id") and str(s.get("template_id")) != str(filters["template_id"]): continue
                
                date_str = s.get("completed_at") or s.get("scheduled_date")
                if not date_str: continue
                
                for ex in s.get("session_exercises") or []:
                    if filters.get("exercise_id") and str(ex.get("exercise_id")) != str(filters["exercise_id"]): continue
                    
                    for log in ex.get("session_logs") or []:
                        val = 0.0
                        if field == "reps":
                            val = float(log.get("actual_reps") or 0)
                        elif field == "weight":
                            val = float(log.get("actual_weight") or 0)
                        elif field == "duration":
                            val = float(log.get("actual_duration_seconds") or 0)
                        elif field == "volume":
                            reps = float(log.get("actual_reps") or 0)
                            weight = float(log.get("actual_weight") or 0)
                            val = reps * weight
                            
                        # Log if > 0 or if we explicitly track duration which can be 0 or small
                        if val > 0 or field == "duration":
                            measurements.append({
                                "id": str(uuid.uuid4()),
                                "user_id": user_id,
                                "kpi_id": kpi_id,
                                "measured_at": date_str,
                                "measured_value": val,
                                "source_reference": {"log_id": log["id"]},
                                "created_at": date_str
                            })
                            
        # Sort measurements descending (newest first)
        measurements.sort(key=lambda x: str(x["measured_at"]), reverse=True)
    except Exception as e:
        print(f"DEBUG: evaluate_dynamic_kpi error: {e}")
        
    return measurements

@router.get("/generate-test-data")
async def generate_test_data(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    import uuid
    from datetime import datetime, timedelta
    
    user_id = current_user["id"]
    
    supabase.table("training_sessions").delete().eq("trainee_id", user_id).execute()
    supabase.table("training_templates").delete().eq("creator_id", user_id).execute()
    supabase.table("exercises").delete().eq("creator_id", user_id).execute()
    
    ex_res = supabase.table("exercises").insert([
        {"name": "Bankdrücken", "creator_id": user_id, "primary_muscle": "Brust"},
        {"name": "Klimmzüge", "creator_id": user_id, "primary_muscle": "Rücken"}
    ]).execute()
    bench_id = [e['id'] for e in ex_res.data if e['name'] == 'Bankdrücken'][0]
    pull_id = [e['id'] for e in ex_res.data if e['name'] == 'Klimmzüge'][0]
    
    tpl_res = supabase.table("training_templates").insert([
        {"name": "Push Day", "creator_id": user_id},
        {"name": "Pull Day", "creator_id": user_id}
    ]).execute()
    push_tpl_id = [t['id'] for t in tpl_res.data if t['name'] == 'Push Day'][0]
    pull_tpl_id = [t['id'] for t in tpl_res.data if t['name'] == 'Pull Day'][0]
    
    now = datetime.now()
    for i in range(5):
        days_ago = (4 - i) * 3
        session_date = (now - timedelta(days=days_ago)).isoformat()
        is_push = i % 2 == 0
        status = "completed" if i < 4 else "missed"
        
        s_res = supabase.table("training_sessions").insert({
            "trainee_id": user_id,      "template_id": push_tpl_id if is_push else pull_tpl_id,
            "status": status,           "scheduled_date": session_date,
            "completed_at": session_date if status == "completed" else None, "feedback_rpe": 8
        }).execute()
        
        session_id = s_res.data[0]["id"]
        if status == "completed":
            se_res = supabase.table("session_exercises").insert({
                "session_id": session_id, "exercise_id": bench_id if is_push else pull_id, "order_index": 1,
            }).execute()
            se_id = se_res.data[0]["id"]
            
            reps_pattern = [5, 4, 4, 3, 2]
            weight = 80 if is_push else 0
            logs = [{"session_exercise_id": se_id, "set_number": set_idx + 1, "actual_reps": reps, "actual_weight": weight, "actual_duration_seconds": 45} for set_idx, reps in enumerate(reps_pattern)]
            supabase.table("session_logs").insert(logs).execute()
            
    return {"status": "ok", "user_id": user_id, "message": "Test data populated successfully!"}

@router.post("/preview", response_model=KPIPreviewResponse)
def preview_kpi(
    params: KPIPreviewRequest,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Zweck: Berechnet eine KPI-Vorschau basierend auf dynamischen Parametern, ohne diese zu speichern.
    Parameter:
        - params: Vorschau-Konfiguration (Abfrage, Zeitraum, Aggregation).
        - current_user: Der anfragende Benutzer.
        - supabase: Der Datenbank-Client.
    Return-Wert: Aktueller Wert, Trend und Historie für die Vorschau.
    Side-Effects: Keine.
    """
    try:
        from datetime import datetime, timedelta, date
        import calendar
        
        # 1. Fetch raw measurements
        all_measurements = evaluate_dynamic_kpi(current_user["id"], "preview-kpi", params.query_config, supabase)
        
        current_val = 0.0
        previous_val = 0.0
        cycle = params.cycle_period
        tt = params.tracking_type

        if all_measurements:
            # A: Determine the measurements for current and previous period
            if cycle in ["daily", "weekly", "monthly", "yearly"]:
                start_curr, end_curr = get_cycle_bounds(cycle)
                # Previous period for trend
                if cycle == "daily": prev_ref = start_curr - timedelta(days=1)
                elif cycle == "weekly": prev_ref = start_curr - timedelta(days=1)
                elif cycle == "monthly": prev_ref = start_curr - timedelta(days=1)
                else: prev_ref = start_curr - timedelta(days=1)
                start_prev, end_prev = get_cycle_bounds(cycle, prev_ref)

                curr_samples = []
                prev_samples = []
                for m in all_measurements:
                    m_dt = datetime.fromisoformat(m["measured_at"].replace('Z', '+00:00')).replace(tzinfo=None)
                    if start_curr <= m_dt <= end_curr: curr_samples.append(float(m["measured_value"]))
                    elif start_prev and start_prev <= m_dt <= end_prev: prev_samples.append(float(m["measured_value"]))
            else:
                since_date = params.start_date or "1970-01-01"
                curr_samples = [float(m["measured_value"]) for m in all_measurements if m["measured_at"] >= since_date]
                prev_samples = [float(m["measured_value"]) for m in all_measurements if m["measured_at"] < since_date]

            # B: Apply Aggregation
            def aggregate(samples, type):
                if not samples: return 0.0
                if type in ["sum", "cumulative"]: return sum(samples)
                if type in ["avg", "average"]: return sum(samples) / len(samples)
                if type in ["max", "max_value"]: return max(samples)
                if type in ["min", "min_value"]: return min(samples)
                return samples[0] # "latest"

            current_val = aggregate(curr_samples, tt)
            previous_val = aggregate(prev_samples, tt)
        
        trend = "stable"
        if current_val > previous_val: trend = "up"
        elif current_val < previous_val: trend = "down"
        
        return KPIPreviewResponse(
            current_value=current_val,
            trend_direction=trend,
            history=all_measurements
        )

    except Exception as e:
        print(f"DEBUG: Preview generation failed: {e}")
        raise HTTPException(status_code=500, detail="Preview generation failed.")

# --- KPI Dashboard ---
@router.get("/dashboard", response_model=List[KPIDashboardItem])
def get_kpi_dashboard(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Zweck: Generiert die aggregierten Dashboard-Daten für alle aktiven KPIs des Benutzers.
    Parameter:
        - current_user: Der Benutzer, für den das Dashboard berechnet wird.
        - supabase: Der Datenbank-Client.
    Return-Wert: Liste von Dashboard-Items (inkl. Fortschritt, Trend und Historie).
    Side-Effects: Keine (Berechnung erfolgt primär im Speicher basierend auf DB-Daten).
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
                continue
                
            kpi_id = t["kpi_id"]
            query_config = kpi_def.get("query_config")
            
            # Use target label or fallback to KPI name
            display_name = t.get("label") or kpi_def.get("name")
            # Use target visualization or fallback to KPI default
            viz_type = t.get("visualization") or kpi_def.get("visualization", "line")
            
            # 2. Fetch recent measurements
            if query_config:
                all_measurements = evaluate_dynamic_kpi(current_user["id"], kpi_id, query_config, supabase)
            else:
                measurements_res = retry_supabase_operation(
                    lambda: supabase.table("kpi_measurements") \
                        .select("*") \
                        .eq("user_id", current_user["id"]) \
                        .eq("kpi_id", kpi_id) \
                        .order("measured_at", desc=True) \
                        .limit(100) \
                        .execute()
                )
                all_measurements = measurements_res.data
            
            current_val = 0.0
            previous_val = 0.0
            cycle = t.get("cycle_period")

            if all_measurements:
                tt = kpi_def.get("tracking_type", "latest")
                
                # A: Determine the measurements for current and previous period
                if cycle in ["daily", "weekly", "monthly", "yearly"]:
                    start_curr, end_curr = get_cycle_bounds(cycle)
                    # Previous period for trend
                    if cycle == "daily": prev_ref = start_curr - timedelta(days=1)
                    elif cycle == "weekly": prev_ref = start_curr - timedelta(days=1)
                    elif cycle == "monthly": prev_ref = start_curr - timedelta(days=1)
                    else: prev_ref = start_curr - timedelta(days=1)
                    start_prev, end_prev = get_cycle_bounds(cycle, prev_ref)

                    curr_samples = []
                    prev_samples = []
                    for m in all_measurements:
                        m_dt = datetime.fromisoformat(m["measured_at"].replace('Z', '+00:00')).replace(tzinfo=None)
                        if start_curr <= m_dt <= end_curr: curr_samples.append(float(m["measured_value"]))
                        elif start_prev and start_prev <= m_dt <= end_prev: prev_samples.append(float(m["measured_value"]))
                else:
                    # All-time / Fixed Date: compare since start_date vs before that?
                    # For simplicity, we compare all measurements since start_date vs older ones
                    since_date = t.get("start_date") or "1970-01-01"
                    if isinstance(since_date, date): since_date = since_date.isoformat()
                    curr_samples = [float(m["measured_value"]) for m in all_measurements if m["measured_at"] >= since_date]
                    prev_samples = [float(m["measured_value"]) for m in all_measurements if m["measured_at"] < since_date]

                # B: Apply Aggregation
                def aggregate(samples, type):
                    if not samples: return 0.0
                    if type == "latest": return samples[0] if samples else 0.0
                    if type == "sum": return sum(samples)
                    if type == "avg": return sum(samples) / len(samples)
                    if type == "max": return max(samples)
                    if type == "min": return min(samples)
                    return samples[0]

                current_val = aggregate(curr_samples, tt)
                previous_val = aggregate(prev_samples, tt)
            
            # 6. Trend calculation: Current vs Previous cycle
            trend = "stable"
            if previous_val > 0:
                if current_val > previous_val: trend = "up"
                elif current_val < previous_val: trend = "down"
            elif cycle == "all_time" and len(all_measurements) >= 2:
                # For all-time, compare latest vs second latest
                if all_measurements[0]["measured_value"] > all_measurements[1]["measured_value"]: trend = "up"
                elif all_measurements[0]["measured_value"] < all_measurements[1]["measured_value"]: trend = "down"

            # 7. Progress calculation based on target mode
            progress = 0.0
            if t.get("target_value") and t.get("target_value") > 0:
                # Progress is (current/target) * 100
                progress = min(100.0, (current_val / t["target_value"]) * 100)
                if t.get("target_mode") == "minimum" and current_val >= t["target_value"]: progress = 100
                elif t.get("target_mode") == "maximum" and current_val <= t["target_value"]: progress = 100
            
            dashboard_items.append(KPIDashboardItem(
                kpi_id=kpi_id,
                name=display_name,
                category=kpi_def["category"],
                unit=kpi_def["unit"],
                visualization=viz_type,
                target=KPITargetResponse(**t),
                current_value=current_val,
                progress_percentage=min(progress, 100.0),
                trend_direction=trend,
                history=[KPIMeasurementResponse(**m) for m in all_measurements[:20]]
            ))
            
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
    """
    Zweck: Löscht einen einzelnen KPI-Messwert.
    Parameter:
        - measurement_id: Die ID des zu löschenden Messwerts.
        - current_user: Der Eigentümer des Messwerts.
        - supabase: Der Datenbank-Client.
    Return-Wert: Erfolgsmeldung.
    Side-Effects: Löscht einen Eintrag in 'kpi_measurements'.
    """
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

@router.patch("/measurements/{measurement_id}", response_model=KPIMeasurementResponse)
def update_kpi_measurement(
    measurement_id: UUID,
    data: dict,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Zweck: Aktualisiert einen bestehenden KPI-Messwert (z.B. Korrektur des Werts).
    Parameter:
        - measurement_id: Die ID des Messwerts.
        - data: Die neuen Daten.
        - current_user: Der Eigentümer des Messwerts.
        - supabase: Der Datenbank-Client.
    Return-Wert: Der aktualisierte Messwert.
    Side-Effects: Modifiziert einen Eintrag in 'kpi_measurements'.
    """
    try:
        # Verify ownership
        check = supabase.table("kpi_measurements").select("user_id").eq("id", str(measurement_id)).single().execute()
        if not check.data or check.data["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized")

        res = supabase.table("kpi_measurements").update(data).eq("id", str(measurement_id)).execute()
        return res.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: update_kpi_measurement error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update measurement: {str(e)}")
