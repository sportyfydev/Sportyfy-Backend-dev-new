"""
SportyFY - KPI Logic Tests
Purpose: Comprehensive verification of KPI aggregation, cycling, and cleanup logic.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from uuid import uuid4

# Import the router functions we want to test
# Since they are tied to FastAPI Depends, we often test them as standalone or override dependencies
from features.feature_kpis import (
    get_kpi_dashboard,
    delete_kpi_target,
    evaluate_dynamic_kpi,
    get_cycle_bounds # Private but we can import for testing if needed or test via get_kpi_dashboard
)

@pytest.fixture
def mock_supabase():
    return MagicMock()

@pytest.fixture
def mock_user():
    return {"id": "test-user-123", "email": "test@example.com"}

def test_cycle_bounds_logic():
    """Verify that daily/weekly/monthly/yearly boundaries are correctly calculated."""
    from features.feature_kpis import get_cycle_bounds
    
    # Thursday, 2026-03-26
    ref_date = datetime(2026, 3, 26, 15, 30)
    
    # 1. Daily
    start, end = get_cycle_bounds("daily", ref_date)
    assert start == datetime(2026, 3, 26, 0, 0)
    assert end == datetime(2026, 3, 27, 0, 0)
    
    # 2. Weekly (Starts Monday in Python/ref_date.weekday() logic)
    # 2026-03-26 is Thursday (weekday 3)
    # Start: 26 - 3 = 23 (Monday)
    start, end = get_cycle_bounds("weekly", ref_date)
    assert start == datetime(2026, 3, 23, 0, 0)
    assert end == datetime(2026, 3, 30, 0, 0)
    
    # 3. Monthly
    start, end = get_cycle_bounds("monthly", ref_date)
    assert start == datetime(2026, 3, 1, 0, 0)
    assert end == datetime(2026, 3, 31, 23, 59, 59)

def test_dashboard_aggregation_types():
    """Verify different aggregation types (sum, avg, max, min, latest) in dashboard."""
    from features.feature_kpis import get_kpi_dashboard
    
    mock_sb = MagicMock()
    # Use valid UUIDs
    uid = str(uuid4())
    kid = str(uuid4())
    tid = str(uuid4())
    user = {"id": uid}
    
    # Setup: 1 Target, with a linked definition
    mock_target = {
        "id": tid, "user_id": uid, "kpi_id": kid, 
        "target_value": 100.0, "target_mode": "minimum",
        "cycle_period": "all_time", "visualization": "line",
        "created_at": datetime.now().isoformat(),
        "is_pinned": False,
        "start_date": "2026-01-01",
        "kpi": {
            "id": kid, "name": "Test KPI", "unit": "kg", "category": "health",
            "tracking_type": "sum", "source_type": "manual", "is_platform": False,
            "user_id": uid, "created_at": datetime.now().isoformat()
        }
    }
    
    # Mock measurements (latest first)
    measurements = [
        {"id": str(uuid4()), "user_id": uid, "kpi_id": kid, "measured_at": "2026-03-26T12:00:00Z", "measured_value": 10.0, "created_at": "2026-03-26T12:00:00Z"},
        {"id": str(uuid4()), "user_id": uid, "kpi_id": kid, "measured_at": "2026-03-25T12:00:00Z", "measured_value": 20.0, "created_at": "2026-03-25T12:00:00Z"},
        {"id": str(uuid4()), "user_id": uid, "kpi_id": kid, "measured_at": "2026-03-24T12:00:00Z", "measured_value": 5.0, "created_at": "2026-03-24T12:00:00Z"}
    ]
    
    def setup_mock_responses(tracking_type):
        mock_target["kpi"]["tracking_type"] = tracking_type
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[mock_target])
        # Measurements query result
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=measurements)

    # 1. SUM: 10 + 20 + 5 = 35
    setup_mock_responses("sum")
    items = get_kpi_dashboard(user, mock_sb)
    assert items[0].current_value == 35.0
    assert items[0].progress_percentage == 35.0 # (35/100) * 100
    
    # 2. MAX: max(10, 20, 5) = 20
    setup_mock_responses("max")
    items = get_kpi_dashboard(user, mock_sb)
    assert items[0].current_value == 20.0
    
    # 3. LATEST: 10
    setup_mock_responses("latest")
    items = get_kpi_dashboard(user, mock_sb)
    assert items[0].current_value == 10.0

def test_delete_target_cleanup_logic():
    """Verify that delete_kpi_target only cleans up definition if last target is removed."""
    from features.feature_kpis import delete_kpi_target
    
    mock_sb = MagicMock()
    
    # Specific mocks for tables
    targets_table = MagicMock()
    defs_table = MagicMock()
    measurements_table = MagicMock()
    
    def table_side_effect(name):
        if name == "kpi_targets": return targets_table
        if name == "kpi_definitions": return defs_table
        if name == "kpi_measurements": return measurements_table
        return MagicMock()
    
    mock_sb.table.side_effect = table_side_effect
    
    uid = str(uuid4())
    user = {"id": uid}
    target_id = uuid4()
    kpi_id = uuid4()
    
    # Case A: Another target still exists
    mock_target = {
        "id": str(target_id), "user_id": uid, "kpi_id": str(kpi_id),
        "kpi": {"id": str(kpi_id), "is_platform": False, "user_id": uid}
    }
    
    # 1. Mock Fetch current target
    targets_table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=mock_target)
    
    # 2. Mock other targets exist (count = 1)
    targets_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": str(uuid4())}])
    
    delete_kpi_target(target_id, user, mock_sb)
    
    # Verify target delete was called
    targets_table.delete.return_value.eq.assert_any_call("id", str(target_id))
    # Ensure definitions were NOT deleted
    defs_table.delete.assert_not_called()

    # Case B: This WAS the last target -> Cleanup measurements and definition
    targets_table.reset_mock()
    defs_table.reset_mock()
    measurements_table.reset_mock()
    
    targets_table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=mock_target)
    targets_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    
    delete_kpi_target(target_id, user, mock_sb)
    
    # Verify definition and measurement delete were called
    defs_table.delete.assert_called_once()
    measurements_table.delete.assert_called_once()

@patch("features.feature_kpis.datetime")
def test_weekly_cycle_trend_calculation(mock_dt):
    """Verify that weekly trend correctly buckets current vs previous week."""
    from features.feature_kpis import get_kpi_dashboard
    
    # Fix 'now' to Thursday 2026-03-26
    mock_dt.now.return_value = datetime(2026, 3, 26, 12, 0)
    mock_dt.fromisoformat = datetime.fromisoformat # Keep original logic
    
    mock_sb = MagicMock()
    uid = str(uuid4())
    user = {"id": uid}
    kid = str(uuid4())
    tid = str(uuid4())
    
    # Target: Weekly cycle, tracking 'sum'
    mock_target = {
        "id": tid, "user_id": uid, "kpi_id": kid, 
        "target_value": 100.0, "target_mode": "minimum",
        "cycle_period": "weekly", "visualization": "line",
        "created_at": datetime.now().isoformat(),
        "is_pinned": False,
        "start_date": "2026-01-01",
        "kpi": {
            "id": kid, "name": "Weekly Vol", "unit": "kg", "category": "training_volume",
            "tracking_type": "sum", "source_type": "automatic_training", "is_platform": False,
            "user_id": uid, "created_at": datetime.now().isoformat()
        }
    }
    
    # Current week: 2026-03-23 to 2026-03-29
    # Previous week: 2026-03-16 to 2026-03-22
    
    measurements = [
        {"id": str(uuid4()), "user_id": uid, "kpi_id": kid, "measured_at": "2026-03-25T12:00:00Z", "measured_value": 100.0, "created_at": "2026-03-25T12:00:00Z"}, # Current week
        {"id": str(uuid4()), "user_id": uid, "kpi_id": kid, "measured_at": "2026-03-24T12:00:00Z", "measured_value": 50.0, "created_at": "2026-03-24T12:00:00Z"},  # Current week -> Total 150
        {"id": str(uuid4()), "user_id": uid, "kpi_id": kid, "measured_at": "2026-03-18T12:00:00Z", "measured_value": 200.0, "created_at": "2026-03-18T12:00:00Z"}  # Previous week -> Total 200
    ]
    
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[mock_target])
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=measurements)
    
    items = get_kpi_dashboard(user, mock_sb)
    
    assert items[0].current_value == 150.0
    assert items[0].trend_direction == "down" # 150 < 200
