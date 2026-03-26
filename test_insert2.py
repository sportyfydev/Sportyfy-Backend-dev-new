import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("SUPABASE_URL="): url = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            if line.startswith("SUPABASE_SERVICE_ROLE_KEY="): key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")

supabase = create_client(url, key)

try:
    row = {
        'exercise_id': None,
        'order_index': 0,
        'group_id': None,
        'target_sets': 1,
        'target_reps': '10 - 8 - 6',
        'target_weight': 50.0,
        'target_rest_seconds': 60,
        'target_duration_seconds': 0,
        'interval_audio_cue': None,
        'interval_visual_color': None,
        'custom_name': 'My exercise',
        'custom_description': None,
        'custom_image_url': None,
        'session_id': 'd31581a8-4263-4706-9a5e-8ccd3309a73e'
    }
    
    res = supabase.table("session_exercises").insert([row]).execute()
    print("Success:", res)
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Error:", e)
    if hasattr(e, 'message'):
        print("Message:", e.message)
