"""
SportyFY - Content Library & Marketplace Browser

Purpose:
This module provides endpoints for browsing public assets, including exercises 
and training templates (marketplace). It focuses on read-only access for 
discovery and initial exploration.

Application Context:
Core feature module for the Exercise Library and Marketplace preview.
Implicitly enforces Supabase Row Level Security (RLS) for data protection.

Data Flow:
User -> feature_content_library.py -> Supabase DB (Exercises & Templates)
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from pydantic import BaseModel
from supabase import Client

from database import get_supabase
from dependencies import get_current_user

router = APIRouter()

# --- Pydantic Models for Output Validation ---

class ExerciseBase(BaseModel):
    """Blueprint for exercise metadata validation."""
    id: str
    name: str
    description: Optional[str] = None
    media_url: Optional[str] = None
    image_url: Optional[str] = None
    default_duration_seconds: Optional[int] = 0
    sport: Optional[str] = None
    muscle_group: Optional[str] = None
    visibility: str

class TemplateBase(BaseModel):
    """Blueprint for training template metadata validation."""
    id: str
    title: str
    description: Optional[str] = None
    visibility: str
    sport: Optional[str] = "Sonstiges"
    difficulty: Optional[str] = "Mittel"
    image_url: Optional[str] = None
    owner_id: str
    owner: Optional[dict] = None


# --- Endpoints ---

@router.get("/exercises", response_model=List[ExerciseBase])
def get_exercises(
    sport: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Fetch accessible exercises based on RLS (owned, platform, or organization).
    
    Args:
        sport (Optional[str]): Optional filter by sport type.
        current_user (dict): The authenticated user context.
        supabase (Client): Injected Supabase client.
        
    Returns:
        List[ExerciseBase]: A list of exercise objects mapped to the Pydantic model.
        
    Side Effects:
        - Executes a SELECT query on the 'exercises' table.
    """
    try:
        # Note: python-supabase handles the auth session if initialized with a token.
        # RLS is enforced on the database level based on the user's role.
        query = supabase.table("exercises") \
            .select("*, owner:users!owner_id(first_name, last_name, email, username)")
        
        # Apply optional filtering.
        if sport:
            query = query.eq("sport", sport)
            
        res = query.execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch exercises: {str(e)}")


@router.get("/marketplace/templates", response_model=List[TemplateBase])
def get_marketplace_templates(
    supabase: Client = Depends(get_supabase)
):
    """
    Fetch public training templates for the Marketplace.
    
    Args:
        supabase (Client): Injected Supabase client.
        
    Returns:
        List[TemplateBase]: A list of public training templates.
        
    Side Effects:
        - Executes a SELECT query on 'training_templates' filtering for visibility='public'.
    """
    try:
        # Marketplace templates are defined as public blueprints.
        res = supabase.table("training_templates") \
            .select("*, owner:users!owner_id(first_name, last_name, email)") \
            .eq("visibility", "public") \
            .execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch marketplace templates: {str(e)}")

