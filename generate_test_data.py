import sys
import os
import uuid
from datetime import datetime, timedelta

import asyncio

async def run_tests():
    from database import get_supabase_client
    supabase = get_supabase_client()
    
    print("=== KPI Engine Test Data Generator ===")
    
    # 1. Sign up test user
    TEST_EMAIL = "kpi.test2@pulse-kinetic.com"
    TEST_PW = "TestPassword123!"
    
    print(f"Signing up test user: {TEST_EMAIL}")
    try:
        auth_res = supabase.auth.sign_up({
            "email": TEST_EMAIL,
            "password": TEST_PW
        })
        print("Sign-up result:", "Success" if auth_res.user else "Failed")
    except Exception as e:
        print(f"Error during sign-up (might already exist): {e}")
        
    # Log in as test user
    login_res = supabase.auth.sign_in_with_password({
        "email": TEST_EMAIL,
        "password": TEST_PW
    })
    
    if not login_res.user:
        print("Failed to log in test user. Aborting.")
        return
        
    user_id = login_res.user.id
    print(f"Test User ID: {user_id}")
    
    # Clean up existing data for this user
    supabase.table("training_sessions").delete().eq("trainee_id", user_id).execute()
    supabase.table("training_templates").delete().eq("creator_id", user_id).execute()
    supabase.table("exercises").delete().eq("creator_id", user_id).execute()
    
    # 2. Setup Base Data
    print("Creating Excerises...")
    ex_res = supabase.table("exercises").insert([
        {"name": "Bankdrücken", "creator_id": user_id, "primary_muscle": "Brust"},
        {"name": "Klimmzüge", "creator_id": user_id, "primary_muscle": "Rücken"}
    ]).execute()
    bench_id = [e['id'] for e in ex_res.data if e['name'] == 'Bankdrücken'][0]
    pull_id = [e['id'] for e in ex_res.data if e['name'] == 'Klimmzüge'][0]
    
    print("Creating Templates...")
    tpl_res = supabase.table("training_templates").insert([
        {"name": "Push Day", "creator_id": user_id},
        {"name": "Pull Day", "creator_id": user_id}
    ]).execute()
    push_tpl_id = [t['id'] for t in tpl_res.data if t['name'] == 'Push Day'][0]
    pull_tpl_id = [t['id'] for t in tpl_res.data if t['name'] == 'Pull Day'][0]
    
    # 3. Insert specific sessions
    print("Generating Sessions and Logs over the last 14 days...")
    
    from random import randint
    now = datetime.now()
    
    # Create 4 completed Push Days and 1 missed Pull Day
    for i in range(5):
        days_ago = (4 - i) * 3  # spread out every 3 days
        session_date = (now - timedelta(days=days_ago)).isoformat()
        
        is_push = i % 2 == 0
        status = "completed" if i < 4 else "missed"
        
        s_res = supabase.table("training_sessions").insert({
            "trainee_id": user_id,
            "template_id": push_tpl_id if is_push else pull_tpl_id,
            "status": status,
            "scheduled_date": session_date,
            "completed_at": session_date if status == "completed" else None,
            "feedback_rpe": 8
        }).execute()
        
        session_id = s_res.data[0]["id"]
        
        if status == "completed":
            # Add exercise
            se_res = supabase.table("session_exercises").insert({
                "session_id": session_id,
                "exercise_id": bench_id if is_push else pull_id,
                "order_index": 1,
            }).execute()
            
            se_id = se_res.data[0]["id"]
            
            # Log 5 sets of (5, 4, 4, 3, 2)
            reps_pattern = [5, 4, 4, 3, 2]
            weight = 80 if is_push else 0 # 80kg bench, 0kg pullups
            
            logs = []
            for set_idx, reps in enumerate(reps_pattern):
                logs.append({
                    "session_exercise_id": se_id,
                    "set_number": set_idx + 1,
                    "actual_reps": reps,
                    "actual_weight": weight,
                    "actual_duration_seconds": 45 # 45 sec per set
                })
            supabase.table("session_logs").insert(logs).execute()
            
    # 4. Run tests
    print("\n--- Running Dynamic KPI Tests ---")
    from features.feature_kpis import evaluate_dynamic_kpi
    
    configs = [
        ("Alle Abgeschlossenen Trainings (Soll = 4)", {
            "entity": "sessions", "field": "count", "filters": {"status": "completed"}
        }),
        ("Alle verpassten Trainings (Soll = 1)", {
            "entity": "sessions", "field": "count", "filters": {"status": "missed"}
        }),
        ("Max Wiederholungen bei Bankdrücken (Soll = 5)", {
            "entity": "logs", "field": "reps", "filters": {"exercise_id": bench_id}
        }),
        ("Summe Volumen Bankdrücken (Soll = ~1440. 3 sessions * 18 reps * 80kg = 4320)", {
            "entity": "logs", "field": "volume", "filters": {"exercise_id": bench_id}
        })
    ]
    
    for title, config in configs:
        res = evaluate_dynamic_kpi(user_id, str(uuid.uuid4()), config, supabase)
        vals = [m["measured_value"] for m in res]
        
        agg_sum = sum(vals)
        agg_max = max(vals) if vals else 0
        agg_min = min(vals) if vals else 0
        
        print(f"\n> {title}")
        print(f"   Raw Values extracted: {vals}")
        print(f"   If Tracking=SUM -> {agg_sum}")
        print(f"   If Tracking=MAX -> {agg_max}")
        print(f"   If Tracking=MIN -> {agg_min}")

if __name__ == "__main__":
    asyncio.run(run_tests())
