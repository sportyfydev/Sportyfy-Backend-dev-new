"""
Unit tests for main.py
"""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_check():
    """
    Test the health check endpoint.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "SportyFY API is operational"}

def test_example_marketplace():
    """
    Test the marketplace example endpoint.
    """
    response = client.get("/api/v1/example-marketplace")
    assert response.status_code == 200
    assert "Marketplace functionality is available" in response.json()["message"]

def test_example_training_sessions():
    """
    Test the training sessions example endpoint.
    """
    response = client.get("/api/v1/example-training-sessions")
    assert response.status_code == 200
    assert "Training Sessions functionality is available" in response.json()["message"]

def test_example_training_templates():
    """
    Test the training templates example endpoint.
    """
    response = client.get("/api/v1/example-training-templates")
    assert response.status_code == 200
    assert "Training Templates functionality is available" in response.json()["message"]

def test_example_kpi_tracking():
    """
    Test the KPI tracking example endpoint.
    """
    response = client.get("/api/v1/example-kpi-tracking")
    assert response.status_code == 200
    assert "KPI Tracking functionality is available" in response.json()["message"]

def test_example_users():
    """
    Test the user management example endpoint.
    """
    response = client.get("/api/v1/example-users")
    assert response.status_code == 200
    assert "User Management functionality is available" in response.json()["message"]
