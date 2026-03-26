"""
SportyFY - Authentication & Authorization Dependencies

Purpose:
This module provides FastAPI dependencies for managing user sessions and permissions.
It verifies JWT tokens against Supabase Auth and enforces role-based access control (RBAC).

Application Context:
Core security layer used by almost all protected API endpoints in the system.

Data Flow:
Inbound Request -> HTTPBearer (Token Extraction) -> get_current_user (Supabase Auth Verify) -> require_role (DB Role Check) -> Protected Route
"""
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import Client
from database import get_supabase

# We use HTTPBearer to automatically extract the "Bearer <token>" from the headers
# or provide an input field in the FastAPI /docs interface.
security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    supabase: Client = Depends(get_supabase)
) -> dict:
    """
    FastAPI dependency that validates the bearer token against Supabase Auth.
    
    Args:
        credentials (HTTPAuthorizationCredentials): Extracted bearer token.
        supabase (Client): Injected Supabase client.
        
    Returns:
        dict: The user's metadata/profile data if authentication is successful.
        
    Raises:
        HTTPException: 401 if the token is invalid, expired, or missing.
        
    Side Effects:
        - Performs a network call to Supabase Auth server.
    """
    token = credentials.credentials
    try:
        # --- PROD SECURITY ---
        # All requests must validate against Supabase Auth.
        # Dev bypasses are strictly prohibited in the security core.
        
        # get_user validates the JWT token cryptographically against the Supabase Auth server.
        # This ensures the token was issued by our specific project and hasn't tampered with.
        user_response = supabase.auth.get_user(token)
        
        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Return only essential fields as a flat dictionary.
        # This prevents potential RecursionErrors when the full Supabase user object
        # (which has complex nested structures) is dumped or printed in logs.
        user = user_response.user
        return {
            "id": user.id,
            "email": user.email,
            "app_metadata": user.app_metadata,
            "user_metadata": user.user_metadata
        }
        
    except Exception as e:
        # Catch any auth errors (parsing, network, protocol drops, etc.)
        # Detailed logging helps distinguish between 'Invalid Token' and 'Supabase Network Error'
        err_msg = str(e)
        logging.error(f"Authentication failed for token [..{token[-10:] if token else 'None'}]: {err_msg}")
        
        if "Server disconnected" in err_msg or "pseudo-header" in err_msg:
             logging.warning("Detected Supabase connection drop/protocol error during Auth. Backend stability might be affected by network conditions.")
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {err_msg if (token and 'fake' in token) else 'Check logs for details'}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_role(allowed_roles: list[str]):
    """
    A dependency factory that creates a dependency to check if the current
    user has one of the required authorization roles in our 'public.users' table.
    
    Args:
        allowed_roles (list[str]): List of roles allowed to access the route (e.g., ['trainer']).
        
    Returns:
        function: A FastAPI-compatible dependency function (role_checker).
    """
    def role_checker(
        current_user: dict = Depends(get_current_user),
        supabase: Client = Depends(get_supabase)
    ):
        """
        The actual dependency function that fetches the user role from the database.
        
        Side Effects:
            - Performs a database query on the 'users' table.
        """
        user_id = current_user.get("id")
        
        # We fetch the role from our custom 'public.users' table because Supabase Auth
        # metadata is harder to update synchronously during role-change operations.
        # This ensures we always have the latest, ground-truth role from our DB.
        response = supabase.table("users").select("role").eq("id", user_id).single().execute()
        
        if not response.data or 'role' not in response.data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User role not found in database. RLS might be blocking access or user missing."
            )
            
        user_role = response.data['role']
        
        # Final authorization check against the provided whitelist.
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required one of: {allowed_roles}, but got {user_role}"
            )
            
        return current_user
        
    return role_checker

