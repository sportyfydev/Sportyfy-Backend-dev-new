"""
SportyFY - Database Connection Manager

Purpose:
This module handles the initialization and management of the Supabase client.
It serves as a central point for database access across the entire backend.

Application Context:
Part of the core infrastructure layer. Initialized during app startup.

Data Flow:
Environment Variables (.env) -> database.py (Client Initialization) -> All feature modules (CRUD operations)
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

# Load environment variables from .env file to ensure connectivity
load_dotenv()

# We prefer using the SERVICE_ROLE_KEY for backend operations to bypass RLS 
# where necessary (e.g., admin tasks), but local dev might use a standard key.
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

# Singleton pattern: Create a single client instance to be reused
_supabase: Client | None = None

def get_supabase() -> Client:
    """
    Returns the initialized Supabase client singleton with increased timeouts.
    """
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError(
                "Missing Supabase credentials. Ensure SUPABASE_URL and SUPABASE_KEY are set."
            )
        
        # Increase timeouts and specify schema to improve stability and performance.
        # This helps prevent 'Server disconnected' errors during high load.
        options = ClientOptions(
            postgrest_client_timeout=30.0,
            storage_client_timeout=30.0,
            schema="public"
        )
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY, options=options)
    
    return _supabase

import time
import logging

def retry_supabase_operation(operation, max_retries=2, delay=1.0):
    """
    Utility wrapper to retry Supabase operations if they fail due to 
    connection drops or 'Server disconnected' errors.
    """
    last_ex = None
    for attempt in range(max_retries + 1):
        try:
            return operation()
        except Exception as e:
            last_ex = e
            err_msg = str(e)
            if "Server disconnected" in err_msg or "pseudo-header" in err_msg or "RemoteProtocolError" in err_msg:
                if attempt < max_retries:
                    logging.warning(f"Supabase connection error (attempt {attempt+1}/{max_retries+1}): {err_msg}. Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
            raise e
    raise last_ex

def verify_connection():
    """
    Helper function to verify the database connection on backend startup.
    Will attempt a simple query to ensure the keys and URL are valid.
    """
    client = get_supabase()
    # Try fetching one feature flag as a connectivity test
    response = retry_supabase_operation(
        lambda: client.table("feature_flags").select("*").limit(1).execute()
    )
    return response.data


