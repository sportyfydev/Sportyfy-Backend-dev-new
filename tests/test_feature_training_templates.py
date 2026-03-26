"""
SportyFY - Training Templates API Unit Tests

Purpose:
This module contains unit tests for the training templates feature, ensuring 
that template creation, listing, and exercise configuration work as expected.

Application Context:
Verification layer for the backend templates module.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

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

def test_create_training_template_success():
    """Test successful creation of a training template."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    mock_response = MagicMock()
    mock_response.data = [{
        "id": "template-uuid", 
        "owner_id": "test-user-uuid", 
        "title": "Strength Plan",
        "created_at": "2026-03-01T00:00:00Z",
        "updated_at": "2026-03-01T00:00:00Z"
    }]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_response
    
    payload = {"title": "Strength Plan", "description": "Classic lifting", "visibility": "private"}
    response = client.post("/api/v1/templates/", json=payload)
    
    assert response.status_code == 200
    assert response.json()["id"] == "template-uuid"
    assert response.json()["title"] == "Strength Plan"
    del app.dependency_overrides[get_supabase]

def test_list_training_templates_success():
    """Test retrieving owned templates."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    mock_response = MagicMock()
    mock_response.data = [
        {
            "id": "t1", "title": "Plan 1", "owner_id": "test-user-uuid",
            "created_at": "2026-03-01T00:00:00Z", "updated_at": "2026-03-01T00:00:00Z"
        },
        {
            "id": "t2", "title": "Plan 2", "owner_id": "test-user-uuid",
            "created_at": "2026-03-01T00:00:00Z", "updated_at": "2026-03-01T00:00:00Z"
        }
    ]
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
    
    response = client.get("/api/v1/templates/")
    
    assert response.status_code == 200
    assert len(response.json()) == 2
    del app.dependency_overrides[get_supabase]

def test_get_training_template_success():
    """Test fetching template details with exercises."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    # Mock template fetch
    mock_template_resp = MagicMock()
    mock_template_resp.data = {
        "id": "t1", 
        "title": "Master Plan", 
        "owner_id": "test-user-uuid",
        "created_at": "2026-03-01T00:00:00Z", 
        "updated_at": "2026-03-01T00:00:00Z"
    }
    # Chain: table().select().eq().single().execute()
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_template_resp
    
    # Mock exercises fetch
    mock_ex_resp = MagicMock()
    mock_ex_resp.data = [{"id": "ex1", "name": "Squats"}]
    # Chain: table().select().eq().order().execute()
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_ex_resp
    
    response = client.get("/api/v1/templates/t1")
    
    assert response.status_code == 200
    assert response.json()["title"] == "Master Plan"
    assert len(response.json()["exercises"]) == 1
    del app.dependency_overrides[get_supabase]

def test_add_template_exercise_success():
    """Test adding an exercise to a template blueprint."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    # OWNERSHIP CHECK MOCK
    mock_owner_resp = MagicMock()
    mock_owner_resp.data = {"owner_id": "test-user-uuid"}
    # table().select().eq().single().execute()
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_owner_resp
    
    # INSERT MOCK
    mock_insert_resp = MagicMock()
    mock_insert_resp.data = [{
        "id": "ex-uuid",
        "template_id": "t1",
        "exercise_id": "pushup",
        "order_index": 0,
        "target_reps": "10",
        "created_at": "2026-03-01T00:00:00Z"
    }]
    # table().insert().execute()
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_insert_resp
    
    payload = {"exercise_id": "pushup", "target_reps": "10", "order_index": 0}
    response = client.post("/api/v1/templates/t1/exercises", json=payload)
    
    assert response.status_code == 200
    assert response.json()["id"] == "ex-uuid"
    del app.dependency_overrides[get_supabase]

def test_add_template_exercise_unauthorized():
    """Test that only the owner can add exercises to a template."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    # Mock ownership check
    mock_verify_resp = MagicMock()
    mock_verify_resp.data = {"owner_id": "different-user-uuid"}
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_verify_resp
    
    payload = {"exercise_id": "pushup", "order_index": 0}
    response = client.post("/api/v1/templates/t1/exercises", json=payload)
    
    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]
    del app.dependency_overrides[get_supabase]
