"""
SportyFY - Training AI API Unit Tests

Purpose:
This module contains unit tests for the training AI feature, ensuring 
that the adaptation logic correctly suggests intensity changes based on 
user performance and RPE.

Application Context:
Verification layer for the backend logic/AI module.
"""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# -------------------------------------------------------------------
# TEST CASES
# -------------------------------------------------------------------

def test_adapt_plan_decrease_intensity():
    """Test scenario: User failed to hit target reps -> Decrease weight."""
    payload = {
        "session_id": "test-sess",
        "target_weight": 100.0,
        "actual_reps": 8,
        "target_reps": 10,
        "rpe_score": 8
    }
    response = client.post("/api/v1/training-ai/adapt-plan", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["suggested_weight"] == 90.0
    assert "Decreasing weight" in data["reasoning"]

def test_adapt_plan_maintain_high_rpe():
    """Test scenario: User hit reps but RPE is very high -> Maintain weight."""
    payload = {
        "session_id": "test-sess",
        "target_weight": 100.0,
        "actual_reps": 10,
        "target_reps": 10,
        "rpe_score": 9
    }
    response = client.post("/api/v1/training-ai/adapt-plan", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["suggested_weight"] == 100.0
    assert "RPE is very high" in data["reasoning"]

def test_adapt_plan_increase_intensity():
    """Test scenario: User hit reps and RPE is low -> Increase intensity."""
    payload = {
        "session_id": "test-sess",
        "target_weight": 100.0,
        "actual_reps": 10,
        "target_reps": 10,
        "rpe_score": 6
    }
    response = client.post("/api/v1/training-ai/adapt-plan", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["suggested_weight"] == 105.0
    assert data["suggested_reps"] == 11
    assert "Increasing weight" in data["reasoning"]

def test_adapt_plan_maintain_normal():
    """Test scenario: Normal execution with balanced RPE -> Maintain."""
    payload = {
        "session_id": "test-sess",
        "target_weight": 100.0,
        "actual_reps": 10,
        "target_reps": 10,
        "rpe_score": 7
    }
    response = client.post("/api/v1/training-ai/adapt-plan", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["suggested_weight"] == 100.0
    assert "Maintain current intensity" in data["reasoning"]
