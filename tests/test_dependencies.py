"""
Unit tests for dependencies.py
"""

import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException, status
from dependencies import get_current_user, require_role

def test_get_current_user_valid_token():
    """
    Test get_current_user with a valid token response from Supabase.
    """
    credentials = MagicMock()
    credentials.credentials = "valid-token"
    
    mock_supabase = MagicMock()
    mock_user = MagicMock()
    # Mock properties as they are accessed in dependencies.py
    mock_user.id = "user-uuid"
    mock_user.email = "test@example.com"
    mock_user.app_metadata = {}
    mock_user.user_metadata = {}
    
    mock_response = MagicMock()
    mock_response.user = mock_user
    mock_supabase.auth.get_user.return_value = mock_response
    
    user = get_current_user(credentials=credentials, supabase=mock_supabase)
    
    assert user["id"] == "user-uuid"
    assert user["email"] == "test@example.com"
    mock_supabase.auth.get_user.assert_called_once_with("valid-token")

def test_get_current_user_invalid_token():
    """
    Test get_current_user with an invalid token response.
    """
    credentials = MagicMock()
    credentials.credentials = "invalid-token"
    
    mock_supabase = MagicMock()
    mock_supabase.auth.get_user.return_value = None
    
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(credentials=credentials, supabase=mock_supabase)
    
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED

def test_require_role_success():
    """
    Test require_role dependency factory - success case.
    """
    allowed_roles = ["trainer", "admin"]
    current_user = {"id": "user-uuid"}
    
    mock_supabase = MagicMock()
    mock_response = MagicMock()
    mock_response.data = {"role": "trainer"}
    mock_supabase.table().select().eq().single().execute.return_value = mock_response
    
    role_checker = require_role(allowed_roles)
    result = role_checker(current_user=current_user, supabase=mock_supabase)
    
    assert result == current_user

def test_require_role_forbidden():
    """
    Test require_role dependency factory - forbidden case.
    """
    allowed_roles = ["admin"]
    current_user = {"id": "user-uuid"}
    
    mock_supabase = MagicMock()
    mock_response = MagicMock()
    mock_response.data = {"role": "trainee"}
    mock_supabase.table().select().eq().single().execute.return_value = mock_response
    
    role_checker = require_role(allowed_roles)
    
    with pytest.raises(HTTPException) as excinfo:
        role_checker(current_user=current_user, supabase=mock_supabase)
    
    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN
