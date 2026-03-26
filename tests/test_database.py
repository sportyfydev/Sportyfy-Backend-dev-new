"""
Unit tests for database.py
"""

import pytest
from unittest.mock import patch, MagicMock
from database import get_supabase, verify_connection

def test_get_supabase_singleton():
    """
    Test that get_supabase returns a singleton instance.
    """
    with patch('database.create_client') as mock_create:
        mock_create.return_value = MagicMock()
        
        # Reset the global singleton for testing
        import database
        database._supabase = None
        
        client1 = get_supabase()
        client2 = get_supabase()
        
        assert client1 == client2
        assert mock_create.call_count == 1

def test_get_supabase_missing_credentials():
    """
    Test that get_supabase raises ValueError when credentials are missing.
    """
    with patch('database.SUPABASE_URL', None), \
         patch('database.SUPABASE_KEY', None):
        
        # Reset the global singleton for testing
        import database
        database._supabase = None
        
        with pytest.raises(ValueError, match="Missing Supabase credentials"):
            get_supabase()

def test_verify_connection():
    """
    Test verify_connection calls the correct supabase methods.
    """
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_limit = MagicMock()
    mock_execute = MagicMock()
    
    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.limit.return_value = mock_limit
    mock_limit.execute.return_value = mock_execute
    mock_execute.data = [{"id": 1, "name": "test_flag"}]
    
    with patch('database.get_supabase', return_value=mock_client):
        result = verify_connection()
        
        assert result == [{"id": 1, "name": "test_flag"}]
        mock_client.table.assert_called_once_with("feature_flags")
