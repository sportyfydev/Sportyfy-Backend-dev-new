import os
import sys
from datetime import date, timedelta
import uuid

# Add backend directory to sys.path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import get_supabase

def create_seeding_data():
    client = get_supabase()
    
    # We will use supabase.auth.admin.list_users() to find the user ID.
    users = client.auth.admin.list_users()
    user_id = None
    for u in users:
        if u.email == "tobsie16@outlook.de":
            user_id = u.id
            break
            
    if not user_id:
        print("User not found: tobsie16@outlook.de. Please create an account first.")
        return
        
    print(f"Found User ID: {user_id}")

    # 2. Create Schwimmen Template
    schwimmen_template = {
        "title": "Schwimm-Training",
        "description": "Ein intensives Schwimmtraining für den gesamten Körper.",
        "visibility": "private",
        "owner_id": user_id
    }
    
    template_resp = client.table("training_templates").insert(schwimmen_template).execute()
    schwimmen_template_id = template_resp.data[0]['id']
    print(f"Created Schwimmen Template: {schwimmen_template_id}")
    
    # Add Schwimmen Exercises (first to exercises table, then link via template_exercises)
    schwimm_ex_data = [
        {"name": "Einschwimmen", "description": "Lockeres Kraulschwimmen zum Aufwärmen.", "sport": "Schwimmen", "owner_id": user_id, "interval_audio_cue": "Schwimmbrille,Badekappe", "target_sets": 1, "target_reps": 1, "rest_time": 60},
        {"name": "50m Sprints", "description": "Schnelle 50 Meter Intervalle Kraulen.", "sport": "Schwimmen", "owner_id": user_id, "interval_audio_cue": "", "target_sets": 5, "target_reps": 1, "rest_time": 60},
        {"name": "Brustschwimmen Technik", "description": "Fokus auf sauberen Beinschlag und Wasserlage.", "sport": "Schwimmen", "owner_id": user_id, "interval_audio_cue": "Schwimmbrett", "target_sets": 4, "target_reps": 1, "rest_time": 30},
        {"name": "Ausschwimmen", "description": "Ganz lockeres Schwimmen am Ende.", "sport": "Schwimmen", "owner_id": user_id, "interval_audio_cue": "", "target_sets": 1, "target_reps": 1, "rest_time": 0}
    ]
    
    for idx, ex in enumerate(schwimm_ex_data):
        # Insert exercise
        ex_resp = client.table("exercises").insert({
            "name": ex["name"],
            "description": ex["description"],
            "sport": ex["sport"],
            "owner_id": ex["owner_id"]
        }).execute()
        ex_id = ex_resp.data[0]["id"]
        
        # Insert template_exercise linking
        client.table("template_exercises").insert({
            "template_id": schwimmen_template_id,
            "exercise_id": ex_id,
            "order_index": idx + 1,
            "target_sets": ex["target_sets"],
            "target_reps": ex["target_reps"],
            "target_rest_seconds": ex["rest_time"],
            "interval_audio_cue": ex["interval_audio_cue"] # Hack to store equipment
        }).execute()

    # 3. Create Template for Fußball
    fussball_template = {
        "title": "Fußball Technik & Ausdauer",
        "description": "5 Übungen für Ballkontrolle und Sprintausdauer auf dem Platz.",
        "visibility": "private",
        "owner_id": user_id
    }
    fb_resp = client.table("training_templates").insert(fussball_template).execute()
    fussball_template_id = fb_resp.data[0]['id']
    print(f"Created Fußball Template: {fussball_template_id}")
    
    fb_ex_data = [
        {"name": "Dribbling Parcours", "description": "Ball eng am Fuß halten durch die Hütchen.", "sport": "Fußball", "owner_id": user_id, "interval_audio_cue": "Fußball,Hütchen", "target_sets": 3, "target_reps": 1, "rest_time": 60},
        {"name": "Torschuss-Training", "description": "Abschlüsse vom Strafraumrand nach kurzem Antritt.", "sport": "Fußball", "owner_id": user_id, "interval_audio_cue": "Fußball,Tor", "target_sets": 4, "target_reps": 10, "rest_time": 90},
        {"name": "Pass-Stafetten", "description": "Direktpass-Spiel an die Wand oder mit Partner.", "sport": "Fußball", "owner_id": user_id, "interval_audio_cue": "Fußball", "target_sets": 3, "target_reps": 20, "rest_time": 45},
        {"name": "Sprint-Intervalle", "description": "20m Sprints mit maximaler Intensität.", "sport": "Fußball", "owner_id": user_id, "interval_audio_cue": "", "target_sets": 5, "target_reps": 1, "rest_time": 120},
        {"name": "Jonglieren", "description": "Ball in der Luft halten, Fokus auf beidfüßigkeit.", "sport": "Fußball", "owner_id": user_id, "interval_audio_cue": "Fußball", "target_sets": 1, "target_reps": 100, "rest_time": 0}
    ]
    
    for idx, ex in enumerate(fb_ex_data):
        ex_resp = client.table("exercises").insert({
            "name": ex["name"],
            "description": ex["description"],
            "sport": ex["sport"],
            "owner_id": ex["owner_id"]
        }).execute()
        ex_id = ex_resp.data[0]["id"]
        
        client.table("template_exercises").insert({
            "template_id": fussball_template_id,
            "exercise_id": ex_id,
            "order_index": idx + 1,
            "target_sets": ex["target_sets"],
            "target_reps": ex["target_reps"],
            "target_rest_seconds": ex["rest_time"],
            "interval_audio_cue": ex["interval_audio_cue"]
        }).execute()

    # 4. Generate Training Sessions for Schwimmen (Tuesdays & Thursdays, 01.03.2026 - 15.04.2026)
    start_date = date(2026, 3, 1)
    end_date = date(2026, 4, 15)
    
    sessions_to_insert = []
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() in [1, 3]: # Tuesday = 1, Thursday = 3
            # We determine status: if date < today, it's completed, else accepted
            status = "accepted" if current_date >= date.today() else "completed"
            completed_at = f"{current_date.isoformat()}T19:00:00+00:00" if status == "completed" else None
            
            sessions_to_insert.append({
                "template_id": schwimmen_template_id,
                "trainee_id": user_id,
                "scheduled_date": current_date.isoformat(),
                "status": status,
                "completed_at": completed_at
            })
        current_date += timedelta(days=1)
        
    # Insert Schwimmen Sessions
    if sessions_to_insert:
        client.table("training_sessions").insert(sessions_to_insert).execute()
        print(f"Inserted {len(sessions_to_insert)} sessions for Schwimmen.")
        
    # 5. Generate one Training Session for Fußball
    # Let's place it next Wednesday
    fb_date = date.today() + timedelta(days=(2 - date.today().weekday()) % 7 + 7) # Next Wednesday
    client.table("training_sessions").insert({
        "template_id": fussball_template_id,
        "trainee_id": user_id,
        "scheduled_date": fb_date.isoformat(),
        "status": "accepted"
    }).execute()
    print("Inserted 1 session for Fußball.")

if __name__ == "__main__":
    create_seeding_data()
