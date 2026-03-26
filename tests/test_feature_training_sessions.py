"""
SportyFY - Training Sessions API Unit Tests

Purpose:
This module contains unit tests for the training sessions feature, ensuring 
that scheduling, instantiation, and workout logging work as expected.

Application Context:
Verification layer for the backend feature modules.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import date

from main import app
from dependencies import get_current_user
from database import get_supabase

client = TestClient(app)

# --- Dependency Overrides ---

def override_get_current_user():
    """Mock the authenticated user."""
    return {"id": "test-user-uuid", "email": "testuser@example.com"}

app.dependency_overrides[get_current_user] = override_get_current_user

# -------------------------------------------------------------------
# TEST CASES
# -------------------------------------------------------------------

def test_create_training_session_success():
    """Test successful scheduling of a self-created session."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    # Mocking Supabase chain
    mock_response = MagicMock()
    mock_response.data = [{
        "id": "session-uuid", 
        "trainee_id": "test-user-uuid", 
        "status": "accepted",
        "created_at": "2026-03-01T00:00:00Z"
    }]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_response
    
    payload = {"scheduled_date": "2026-03-10", "scheduled_time": "10:00"}
    response = client.post("/api/v1/sessions/", json=payload)
    
    assert response.status_code == 200
    assert response.json()["id"] == "session-uuid"
    assert response.json()["status"] == "accepted"
    del app.dependency_overrides[get_supabase]

def test_get_upcoming_sessions_success():
    """Test fetching upcoming sessions with template join."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    mock_response = MagicMock()
    # In Supabase joins, the joined table is a nested dict
    mock_response.data = [
        {
            "id": "s1",
            "scheduled_date": "2026-03-20",
            "status": "accepted",
            "assigned_by": None,
            "trainee_id": "test-user-uuid",
            "created_at": "2026-03-01T00:00:00Z",
            "template": {"title": "Full Body Burn", "description": "High intensity"}
        }
    ]
    # Chain: table().select().eq().in_().gte().order().limit().execute()
    mock_supabase.table.return_value.select.return_value.eq.return_value.in_.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
    
    response = client.get("/api/v1/sessions/upcoming?limit=1")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Full Body Burn"
    assert data[0]["is_trainer_assigned"] is False
    del app.dependency_overrides[get_supabase]

def test_instantiate_session_success():
    """Test creating a session instance from a template with exercises."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    # 1. Mock template fetch
    mock_template_resp = MagicMock()
    mock_template_resp.data = {"id": "template-uuid"}
    # Chain for single template check
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_template_resp
    
    # 2. Mock exercises fetch
    mock_ex_resp = MagicMock()
    mock_ex_resp.data = [{"id": "ex-temp-1", "exercise_id": "pushup", "order_index": 0}]
    
    # 3. Mock session insert
    mock_session_resp = MagicMock()
    mock_session_resp.data = [{
        "id": "new-session-uuid",
        "trainee_id": "test-user-uuid",
        "created_at": "2026-03-01T00:00:00Z"
    }]
    
    # Setup for multiple calls
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_ex_resp
    mock_supabase.table.return_value.insert.return_value.execute.side_effect = [
        mock_session_resp, # session header
        MagicMock(data=[]) # exercise snapshots
    ]
    
    response = client.post("/api/v1/sessions/instantiate/template-uuid")
    if response.status_code != 200:
        print("ERROR INSTANTIATE:", response.json())
    
    assert response.status_code == 200
    assert response.json()["id"] == "new-session-uuid"
    assert mock_supabase.table.return_value.insert.call_count == 2
    del app.dependency_overrides[get_supabase]

def test_get_training_session_unauthorized():
    """Test that users cannot view sessions they don't own."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    mock_response = MagicMock()
    mock_response.data = {"id": "other-session", "trainee_id": "different-user-uuid"}
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response
    
    response = client.get("/api/v1/sessions/other-session")
    
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]
    del app.dependency_overrides[get_supabase]

def test_complete_session_success():
    """Test marking a session as completed with RPE feedback."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    # Verify ownership mock
    mock_verify_resp = MagicMock()
    mock_verify_resp.data = {"trainee_id": "test-user-uuid"}
    # table().select().eq().single().execute()
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_verify_resp
    
    # Update mock
    mock_update_resp = MagicMock()
    mock_update_resp.data = [{
        "id": "sess-1", 
        "status": "completed", 
        "feedback_rpe": 9,
        "trainee_id": "test-user-uuid",
        "created_at": "2026-03-01T00:00:00Z"
    }]
    # table().update().eq().execute()
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_update_resp
    
    response = client.patch("/api/v1/sessions/sess-1/complete", json={"feedback_rpe": 9})
    
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "completed"
    assert response.json()["data"]["feedback_rpe"] == 9
    # Cleanup
    del app.dependency_overrides[get_supabase]

def test_complete_session_invalid_rpe():
    """Test validation for RPE score (must be 1-10)."""
    response = client.patch("/api/v1/sessions/sess-1/complete", json={"feedback_rpe": 0})
    assert response.status_code == 422
    
    response = client.patch("/api/v1/sessions/sess-1/complete", json={"feedback_rpe": 11})
    assert response.status_code == 422

def test_list_training_sessions_success():
    """Test retrieving all sessions for the trainee."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    mock_response = MagicMock()
    mock_response.data = [
        {"id": "s1", "trainee_id": "test-user-uuid", "status": "completed", "created_at": "2026-03-01T00:00:00Z", "template": {}},
        {"id": "s2", "trainee_id": "test-user-uuid", "status": "accepted", "created_at": "2026-03-01T00:00:00Z", "template": {}}
    ]
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_response
    
    response = client.get("/api/v1/sessions/")
    assert response.status_code == 200
    assert len(response.json()) == 2
    del app.dependency_overrides[get_supabase]

def test_get_training_session_success():
    """Test fetching a full session detail with exercises."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    # Session fetch
    mock_sess_resp = MagicMock()
    mock_sess_resp.data = {"id": "s1", "trainee_id": "test-user-uuid"}
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_sess_resp
    
    # Exercises fetch
    mock_ex_resp = MagicMock()
    mock_ex_resp.data = [{"id": "ex1", "order_index": 0}]
    # Chain: table().select().eq().order().execute()
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_ex_resp
    
    response = client.get("/api/v1/sessions/s1")
    assert response.status_code == 200
    assert "exercises" in response.json()
    del app.dependency_overrides[get_supabase]

def test_add_session_exercise_success():
    """Test adding an exercise snapshot to an active session."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    # Ownership check
    mock_owner_resp = MagicMock()
    mock_owner_resp.data = {"trainee_id": "test-user-uuid"}
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_owner_resp
    
    # Insert
    mock_insert_resp = MagicMock()
    mock_insert_resp.data = [{
        "id": "ex-uuid",
        "session_id": "s1",
        "exercise_id": "benchpress",
        "order_index": 1,
        "target_reps": "12",
        "created_at": "2026-03-01T00:00:00Z"
    }]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_insert_resp
    
    payload = {"exercise_id": "benchpress", "target_reps": "12", "order_index": 1}
    response = client.post("/api/v1/sessions/s1/exercises", json=payload)
    if response.status_code != 200:
        print("ERROR ADD EXERCISE:", response.json())
    assert response.status_code == 200
    assert response.json()["id"] == "ex-uuid"
    del app.dependency_overrides[get_supabase]

def test_log_exercise_set_success():
    """Test logging performance for a set with ownership verification."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    # 1. Mock Ownership Check (select with inner join)
    mock_check_resp = MagicMock()
    mock_check_resp.data = {
        "id": "ex1",
        "training_sessions": {"trainee_id": "test-user-uuid"}
    }
    # Chain: table().select().eq().single().execute()
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_check_resp
    
    # 2. Mock Insert
    mock_insert_resp = MagicMock()
    mock_insert_resp.data = [{
        "id": "log-uuid",
        "session_exercise_id": "ex1",
        "set_number": 1,
        "actual_reps": 10,
        "actual_weight": 60.5,
        "created_at": "2026-03-01T00:00:00Z"
    }]
    # Chain for insert: table().insert().execute()
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_insert_resp
    
    payload = {"set_number": 1, "actual_reps": 10, "actual_weight": 60.5}
    response = client.post("/api/v1/sessions/exercises/ex1/logs", json=payload)
    
    assert response.status_code == 200
    assert response.json()["id"] == "log-uuid"
    assert mock_supabase.table.return_value.select.called
    del app.dependency_overrides[get_supabase]

