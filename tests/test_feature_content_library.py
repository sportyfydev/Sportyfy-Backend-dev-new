"""
SportyFY - Content Library API Unit Tests

Purpose:
This module contains unit tests for the content library feature, ensuring 
that exercise browsing and marketplace template discovery work as expected.

Application Context:
Verification layer for the backend content library module.
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

def test_get_exercises_success():
    """Test retrieving exercises with optional sport filter."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    mock_response = MagicMock()
    mock_response.data = [
        {"id": "ex1", "name": "Pushups", "sport": "Fitness", "visibility": "public"},
        {"id": "ex2", "name": "Squats", "sport": "Fitness", "visibility": "public"}
    ]
    # Correct Chaining for Supabase Mock
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
    
    response = client.get("/api/v1/content/exercises?sport=Fitness")
    
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["name"] == "Pushups"
    # Cleanup
    del app.dependency_overrides[get_supabase]

def test_get_marketplace_templates_success():
    """Test retrieving public marketplace templates."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    mock_response = MagicMock()
    mock_response.data = [
        {"id": "t1", "title": "Public Plan", "visibility": "public", "owner_id": "admin"}
    ]
    # Table -> Select -> Eq -> Execute
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
    
    response = client.get("/api/v1/content/marketplace/templates")
    
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Public Plan"
    # Cleanup
    del app.dependency_overrides[get_supabase]

def test_get_exercises_error():
    """Test error handling during exercise retrieval."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    # Simulate DB error at the very beginning of the chain
    mock_supabase.table.side_effect = Exception("DB Connection Timeout")
    
    response = client.get("/api/v1/content/exercises")
    
    assert response.status_code == 500
    assert "DB Connection Timeout" in response.json()["detail"]
    # Cleanup
    del app.dependency_overrides[get_supabase]
