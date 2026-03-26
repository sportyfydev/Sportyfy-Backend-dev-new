"""
Unit tests for feature_metrics.py
"""

import pytest
from unittest.mock import MagicMock
from fastapi import status, HTTPException
from features.feature_metrics import (
    log_body_metric, get_body_metrics, 
    get_user_goals, upsert_user_goals,
    get_user_preferences, update_user_preferences
)
from features.schemas_metrics import BodyMetricCreate, UserGoalUpdate, UserPreferencesUpdate
import datetime

def test_log_body_metric_success():
    current_user = {"id": "user-uuid"}
    mock_supabase = MagicMock()
    metric_in = BodyMetricCreate(weight_kg=80.5, body_fat_percent=15.0, date=datetime.date(2026, 3, 9))
    
    # Mocking response
    mock_response = MagicMock()
    mock_response.data = [{"id": "metric-uuid", "user_id": "user-uuid", "weight_kg": 80.5, "body_fat_percent": 15.0, "date": "2026-03-09", "created_at": "2026-03-09T12:00:00Z", "updated_at": "2026-03-09T12:00:00Z"}]
    # SETUP WITHOUT CALLING:
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_response
    
    result = log_body_metric(metric_in=metric_in, current_user=current_user, supabase=mock_supabase)
    
    assert result["weight_kg"] == 80.5
    # Verify the first (and only) call to table() was with "body_metrics"
    mock_supabase.table.assert_called_with("body_metrics")

def test_get_body_metrics_success():
    current_user = {"id": "user-uuid"}
    mock_supabase = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [{"id": "uuid1"}, {"id": "uuid2"}]
    # Chain setup
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
    
    result = get_body_metrics(limit=10, current_user=current_user, supabase=mock_supabase)
    
    assert len(result) == 2
    mock_supabase.table.return_value.select.assert_called_with("*")

def test_get_user_goals_skeleton_fallback():
    current_user = {"id": "user-uuid"}
    mock_supabase = MagicMock()
    mock_response = MagicMock()
    mock_response.data = []
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
    
    result = get_user_goals(current_user=current_user, supabase=mock_supabase)
    
    assert result["id"] == "00000000-0000-0000-0000-000000000000"
    assert result["target_weight_kg"] is None

def test_upsert_user_goals_success():
    current_user = {"id": "user-uuid"}
    mock_supabase = MagicMock()
    goals_in = UserGoalUpdate(target_weight_kg=75.0)
    
    mock_response = MagicMock()
    mock_response.data = [{"user_id": "user-uuid", "target_weight_kg": 75.0}]
    mock_supabase.table.return_value.upsert.return_value.execute.return_value = mock_response
    
    result = upsert_user_goals(goals_in=goals_in, current_user=current_user, supabase=mock_supabase)
    
    assert result["target_weight_kg"] == 75.0
    mock_supabase.table.return_value.upsert.assert_called_once()

def test_get_user_preferences_fallback():
    current_user = {"id": "user-uuid"}
    mock_supabase = MagicMock()
    mock_response = MagicMock()
    mock_response.data = []
    mock_supabase.table().select().eq().execute.return_value = mock_response
    
    result = get_user_preferences(current_user=current_user, supabase=mock_supabase)
    
    assert result["dashboard_layout"] == []

def test_update_user_preferences_success():
    current_user = {"id": "user-uuid"}
    mock_supabase = MagicMock()
    prefs_in = UserPreferencesUpdate(dashboard_layout=[{"id": "kpi1", "visible": True}])
    
    mock_response = MagicMock()
    mock_response.data = [{"user_id": "user-uuid", "dashboard_layout": [{"id": "kpi1", "visible": True}]}]
    mock_supabase.table().upsert().execute.return_value = mock_response
    
    result = update_user_preferences(prefs_in=prefs_in, current_user=current_user, supabase=mock_supabase)
    
    assert len(result["dashboard_layout"]) == 1
