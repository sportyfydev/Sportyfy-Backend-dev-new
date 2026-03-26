"""
Simulate E2E Flow for Phase 3 Validations
-----------------------------------------
This script programmatically acts as an API client to test the entire Phase 3 feature flow.

Run this script while the FastAPI server is running (`uvicorn main:app --reload`).
"""

import httpx
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def get_auth_headers():
    return {"Authorization": "Bearer fake-dev-token"}

def setup_dev_user_and_exercise():
    # We do not have SQLAlchemy or a Supabase Service Key to bypass RLS programmatically.
    # Therefore, we rely on the user having run the setup script or manually inserting data.
    
    user_id = "58b08fce-9d8c-4210-841f-8a84d7d46a13"
    ex_id = "00000000-0000-0000-0000-000000000001"
    
    import httpx
    # Simple check if the auth bypass actually works before proceeding
    with httpx.Client(base_url=BASE_URL, headers=get_auth_headers(), timeout=5.0) as client:
        r = client.get("/api/v1/kpi/summary")
        if r.status_code == 401 or r.status_code == 403:
             print("ERROR: Dev Auth bypass is rejecting the token.")
             print("Make sure `dependencies.py` has the DEV BYPASS block for 'fake-dev-token' enabled.")
             return None, None
             
        # Optional: We could hit a public endpoint to verify the exercise exists if we had one.
        # For now, we just assume the user has set it up via `setup_mock_db.py` logic or manually.
        
    return user_id, ex_id

def run_simulation():
    print("==================================================")
    print("SportyFY - Phase 3 E2E Flow Simulation")
    print("==================================================")
    
    user_id, ex_id = setup_dev_user_and_exercise()
    if not user_id:
        print("Failed to setup DB prerequisites.")
        sys.exit(1)
        
    with httpx.Client(base_url=BASE_URL, headers=get_auth_headers(), timeout=10.0) as client:
        
        # 1. Check API Health
        print("\n[✓] 1. Checking API Health...")
        try:
            r = client.get("/health")
            if r.status_code != 200:
                print(f"Error: API is not running correctly. {r.text}")
                sys.exit(1)
            print("API is healthy.")
        except httpx.ConnectError:
            print("Error: Could not connect to API. Is uvicorn running?")
            sys.exit(1)

        # 2. Create a Training Template
        print("\n[✓] 2. Creating a Training Template...")
        template_payload = {
            "title": "E2E Test Workout: Push Day",
            "description": "A programmatic test workout",
            "visibility": "private"
        }
        r = client.post("/api/v1/templates/", json=template_payload)
        if r.status_code != 200:
            print(f"Failed to create template: {r.text}")
            sys.exit(1)
            
        template = r.json()
        template_id = template["id"]
        print(f"Template Created! ID: {template_id}")

        # 3. Instantiate a Session from the Template
        print("\n[✓] 3. Instantiating a Session from the Template...")
        r = client.post(f"/api/v1/sessions/instantiate/{template_id}")
        if r.status_code != 200:
            print(f"Failed to instantiate session: {r.text}")
            sys.exit(1)
            
        session = r.json()
        session_id = session["id"]
        print(f"Session Instantiated! ID: {session_id}")

        # 4. Add a custom exercise to the instantiated session directly (optional customization)
        print("\n[✓] 4. Adding a specific exercise to the active session...")
        ex_payload = {
            "exercise_id": ex_id, 
            "order_index": 1,
            "target_sets": 3,
            "target_reps": 10
        }
        r = client.post(f"/api/v1/sessions/{session_id}/exercises", json=ex_payload)
        if r.status_code != 200:
            print(f"Failed to add exercise: {r.text}")
            sys.exit(1)
            
        session_exercise = r.json()
        s_ex_id = session_exercise["id"]
        print(f"Exercise added to session! Session_Exercise_ID: {s_ex_id}")

        # 5. Log Sets (Actual lifting data)
        print("\n[✓] 5. Logging Sets for the exercise...")
        logs = [
            {"set_number": 1, "actual_reps": 10, "actual_weight": 60.0},
            {"set_number": 2, "actual_reps": 10, "actual_weight": 65.0},
            {"set_number": 3, "actual_reps": 8, "actual_weight": 70.0}
        ]
        total_vol = 0
        for log in logs:
            r = client.post(f"/api/v1/sessions/exercises/{s_ex_id}/logs", json=log)
            if r.status_code != 200:
                print(f"Failed to log set {log['set_number']}: {r.text}")
                sys.exit(1)
            print(f"   Logged Set {log['set_number']}: {log['actual_reps']} reps @ {log['actual_weight']}kg")
            total_vol += (log["actual_reps"] * log["actual_weight"])
        print(f"Expected generated volume: {total_vol}kg")

        # 6. Mark Session as Completed
        print("\n[✓] 6. Marking Session as Completed...")
        comp_payload = {"feedback_rpe": 8}
        r = client.patch(f"/api/v1/sessions/{session_id}/complete", json=comp_payload)
        if r.status_code != 200:
            print(f"Failed to complete session: {r.text}")
            sys.exit(1)
        print("Session completed successfully with RPE 8.")

        # 7. Fetch KPIs
        print("\n[✓] 7. Fetching User KPI Summary...")
        r = client.get("/api/v1/kpi/summary")
        if r.status_code != 200:
            print(f"Failed to fetch KPIs: {r.text}")
            sys.exit(1)
            
        kpis = r.json()
        print("\n================ KPI SUMMARY ================")
        print(f"Total Completed Workouts: {kpis['total_workouts_completed']}")
        print(f"Total Volume Lifted:      {kpis['total_volume_kg']} kg")
        print("=============================================")
        
        print("\n✅ Simulation Completed Successfully!")

if __name__ == "__main__":
    run_simulation()
