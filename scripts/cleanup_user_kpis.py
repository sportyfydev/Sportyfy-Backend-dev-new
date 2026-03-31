
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
if not url or not key:
    print("Environment variables SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not found.")
    exit(1)

supabase = create_client(url, key)

email = "tobsie16@outlook.de"
user_res = supabase.table("users").select("id").eq("email", email).execute()
if not user_res.data:
    print(f"User {email} not found")
    exit(1)

user_id = user_res.data[0]["id"]
print(f"Cleaning up for user {user_id} ({email})...")

# 1. Delete ALL measurements for this user that belong to MANUAL definitions
# First find manual definition IDs
manual_defs = supabase.table("kpi_definitions").select("id").eq("user_id", user_id).eq("source_type", "manual").execute()
manual_ids = [d["id"] for d in manual_defs.data] if manual_defs.data else []

if manual_ids:
    res_m = supabase.table("kpi_measurements").delete().eq("user_id", user_id).in_("kpi_id", manual_ids).execute()
    print(f"Deleted {len(res_m.data)} measurements for manual KPIs.")
else:
    print("No manual definitions found, skipping measurement deletion.")

# 2. Delete ALL targets (cards) for this user to start fresh
res_t = supabase.table("kpi_targets").delete().eq("user_id", user_id).execute()
print(f"Deleted {len(res_t.data)} targets (dashboard cards).")

# 3. Delete the manual definitions themselves
if manual_ids:
    res_d = supabase.table("kpi_definitions").delete().eq("user_id", user_id).eq("source_type", "manual").execute()
    print(f"Deleted {len(res_d.data)} manual definitions.")
