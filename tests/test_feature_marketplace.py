"""
SportyFY - Marketplace API Unit Tests

Purpose:
This module contains unit tests for the marketplace feature, ensuring 
that listing items, detailed retrieval, and order creation work as expected.

Application Context:
Verification layer for the backend marketplace module.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from main import app
from dependencies import get_current_user, require_role
from database import get_supabase

client = TestClient(app)

# --- Dependency Overrides ---

def override_get_current_user():
    """Mock the authenticated user."""
    return {"id": "test-user-uuid", "email": "testuser@example.com"}

def override_require_role(roles):
    """Mock the role requirement dependency."""
    def dependency():
        return {"id": "creator-uuid", "role": "creator"}
    return dependency

app.dependency_overrides[get_current_user] = override_get_current_user
# We need to handle the factory require_role differently if used in Depends
# For simplicity in 1-to-1 testing, we'll patch it in the test methods.

# -------------------------------------------------------------------
# TEST CASES
# -------------------------------------------------------------------

def test_list_marketplace_items_success():
    """Test retrieving all marketplace items."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    mock_response = MagicMock()
    mock_response.data = [{"id": "item1", "title": "Guide 1"}, {"id": "item2", "title": "Guide 2"}]
    mock_supabase.table.return_value.select.return_value.execute.return_value = mock_response
    
    response = client.get("/api/v1/marketplace/")
    
    assert response.status_code == 200
    assert len(response.json()) == 2
    del app.dependency_overrides[get_supabase]

def test_get_marketplace_item_success():
    """Test fetching a specific marketplace item."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    mock_response = MagicMock()
    mock_response.data = {"id": "item1", "title": "Special Guide"}
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response
    
    response = client.get("/api/v1/marketplace/item1")
    
    assert response.status_code == 200
    assert response.json()["title"] == "Special Guide"
    del app.dependency_overrides[get_supabase]

def test_create_marketplace_item_success():
    """Test creating a marketplace item with creator role."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    # Mock Role Check: require_role calls supabase.table("users").select("role")...
    mock_role_resp = MagicMock()
    mock_role_resp.data = {"role": "creator"}
    # Mock Item Insertion
    mock_insert_resp = MagicMock()
    mock_insert_resp.data = [{"id": "new-item-id"}]
    
    # We use side_effect to return role check first, then insertion
    # Chain for role check: table().select().eq().single().execute()
    # Chain for insert: table().insert().execute()
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_role_resp
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_insert_resp
    
    payload = {"title": "New Program", "price": 29.99}
    response = client.post("/api/v1/marketplace/", json=payload, headers={"Authorization": "Bearer fake-dev-token"})
    if response.status_code != 200:
        print("ERROR MARKETPLACE:", response.json())
    
    assert response.status_code == 200
    assert "successfully" in response.json()["message"]
    del app.dependency_overrides[get_supabase]

def test_create_order_success():
    """Test creating an order for an item."""
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    mock_response = MagicMock()
    mock_response.data = [{"id": "order-id"}]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_response
    
    payload = {"item_id": "item1", "quantity": 1}
    response = client.post("/api/v1/marketplace/orders", json=payload)
    if response.status_code != 200:
        print("ERROR ORDER:", response.json())
    
    assert response.status_code == 200
    assert "Order created" in response.json()["message"]
    del app.dependency_overrides[get_supabase]
