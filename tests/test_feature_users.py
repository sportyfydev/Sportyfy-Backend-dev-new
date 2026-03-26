"""
Unit tests for feature_users.py
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import status, HTTPException
from features.feature_users import delete_my_account

def test_delete_my_account_dev_bypass():
    """
    Test the dev-bypass logic for account deletion.
    """
    current_user = {"id": "58b08fce-9d8c-4210-841f-8a84d7d46a13"}
    mock_supabase = MagicMock()
    
    # Logic returns None/void on success, so we just ensure it doesn't fail
    result = delete_my_account(current_user=current_user, supabase=mock_supabase)
    
    assert result is None
    # Ensure the admin delete was NOT called
    assert mock_supabase.auth.admin.delete_user.call_count == 0

def test_delete_my_account_success():
    """
    Test successful account deletion via Supabase Admin API.
    """
    current_user = {"id": "real-user-uuid"}
    mock_supabase = MagicMock()
    
    delete_my_account(current_user=current_user, supabase=mock_supabase)
    
    mock_supabase.auth.admin.delete_user.assert_called_once_with("real-user-uuid")

def test_delete_my_account_failure():
    """
    Test account deletion failure handling.
    """
    current_user = {"id": "real-user-uuid"}
    mock_supabase = MagicMock()
    mock_supabase.auth.admin.delete_user.side_effect = Exception("Supabase Error")
    
    with pytest.raises(HTTPException) as excinfo:
        delete_my_account(current_user=current_user, supabase=mock_supabase)
        
    assert excinfo.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Failed to delete account" in excinfo.value.detail
