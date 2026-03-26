"""
Unit tests for the KPI Tracking API endpoints.
"""

from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from main import app
from dependencies import get_current_user
from database import get_supabase

client = TestClient(app)

# --- Mock Dependency Overrides ---

def override_get_current_user():
    return {"id": "test-user-id", "email": "testuser@example.com"}

app.dependency_overrides[get_current_user] = override_get_current_user

# --- Mock Supabase Table Responses ---

class MockSupabaseTable:
    def __init__(self, table_name):
        self.table_name = table_name
        self.mock_data = []

    def select(self, *args, **kwargs):
        return self

    def eq(self, column, value):
        # We can implement simple matching logic if needed, or just return static
        return self
        
    def in_(self, column, values):
        return self

    def single(self):
        return self

    def execute(self):
        class MockResponse:
            pass
        resp = MockResponse()
        
        if self.table_name == "training_sessions":
            resp.data = [{"id": "session-1", "completed_at": "2026-03-01T12:00:00Z"}]
        elif self.table_name == "session_exercises":
            resp.data = [{"id": "s-ex-1", "session_id": "session-1", "exercise_id": "test-ex"}]
        elif self.table_name == "session_logs":
            resp.data = [
                {"session_exercise_id": "s-ex-1", "actual_reps": 10, "actual_weight": 100.0},
                {"session_exercise_id": "s-ex-1", "actual_reps": 8, "actual_weight": 105.0} # Max weight
            ]
        else:
            resp.data = []
            
        return resp

class MockSupabaseClient:
    def table(self, name: str):
        return MockSupabaseTable(name)

# --- Test Cases ---

def test_get_kpi_summary():
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    # 1. Mock sessions response
    mock_sessions_res = MagicMock()
    mock_sessions_res.data = [{"id": "s1"}]
    
    # 2. Mock exercises response
    mock_exercises_res = MagicMock()
    mock_exercises_res.data = [{"id": "ex1"}]
    
    # 3. Mock logs (the actual volume)
    mock_logs_res = MagicMock()
    mock_logs_res.data = [
        {"actual_reps": 10, "actual_weight": 100.0},
        {"actual_reps": 8, "actual_weight": 105.0}
    ]
    
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_sessions_res
    mock_supabase.table.return_value.select.return_value.in_.return_value.execute.side_effect = [
        mock_exercises_res,
        mock_logs_res
    ]
    
    response = client.get("/api/v1/kpi/summary")
    if response.status_code != 200:
        print("ERROR:", response.json())
    assert response.status_code == 200
    
    data = response.json()
    assert data["total_workouts_completed"] == 1
    # 10*100 = 1000 + 8*105 = 840 -> Total: 1840
    assert data["total_volume_kg"] == 1840.0

def test_get_exercise_progress():
    mock_supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    
    # 1. Mock sessions
    mock_sessions = MagicMock(data=[{"id": "s1", "completed_at": "2026-03-01T12:00:00Z"}])
    # 2. Mock exercise instances
    mock_exercises = MagicMock(data=[{"id": "ei1", "session_id": "s1"}])
    # 3. Mock logs
    mock_logs = MagicMock(data=[{"session_exercise_id": "ei1", "actual_weight": 105.0}])
    
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_sessions
    mock_supabase.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = mock_exercises
    mock_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value = mock_logs
    
    response = client.get("/api/v1/kpi/exercise/test-ex")
    if response.status_code != 200:
        print("ERROR:", response.json())
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 1
    assert data[0]["max_weight"] == 105.0
    assert data[0]["session_date"] == "2026-03-01T12:00:00Z"
    del app.dependency_overrides[get_supabase]
