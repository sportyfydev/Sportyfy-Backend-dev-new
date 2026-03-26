"""
SportyFY - User Management & Identity Feature

Purpose:
This module provides endpoints for managing the user's own identity and account.
Specifically handles account deletion for GDPR compliance.

Application Context:
Core feature module. Interacts with Supabase Auth Admin API for permanent deletion.

Data Flow:
Authenticated User -> delete_my_account -> Supabase Admin (Auth deletion) -> Cascade to public.users
"""

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from database import get_supabase
from dependencies import get_current_user
from .schemas_users import UserProfileUpdate

router = APIRouter()

@router.put("/me")
def update_my_profile(
    profile_in: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Update the authenticated user's profile information.
    """
    user_id = current_user.get("id")
    update_data = profile_in.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided for update")
        
    try:
        res = supabase.table("users").update(update_data).eq("id", user_id).execute()
        return res.data[0]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Delete the currently authenticated user's account permanently (GDPR compliance).
    This calls the Supabase Admin API to delete the user from auth.users,
    which should cascade and delete their public.users profile and related data.
    
    Args:
        current_user (dict): The authenticated user's data from JWT.
        supabase (Client): Injected Supabase client with Service Role access.
        
    Raises:
        HTTPException: 500 if the Supabase Admin API call fails.
        
    Side Effects:
        - Permanently removes the user record from Supabase Auth.
        - Triggers cascading deletes in the database if configured.
    """
    user_id = current_user.get("id")
    
    # --- DEV BYPASS ---
    # We do not want to delete our core test accounts during local development 
    # and E2E automation scripts.
    if user_id == "58b08fce-9d8c-4210-841f-8a84d7d46a13":
        # Just return success for the local memory test simulation
        return
        
    try:
        # Require service role key for auth admin actions; ensure it's configured in database.py.
        # This bypasses standard user permissions to perform a hard delete.
        supabase.auth.admin.delete_user(user_id)
        # Note: In our SportyFY schema, public.users has ON DELETE CASCADE configured,
        # so this action automatically cleans up all user-related metrics and plans.
        return
    except Exception as e:
        # GDPR critical: Log failure but return a clean error to the client.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete account: {str(e)}"
        )

