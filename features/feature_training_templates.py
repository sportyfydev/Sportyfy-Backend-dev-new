"""
SportyFY - Training Templates Feature

Purpose:
This module provides endpoints for managing reusable workout plans (templates).
Templates serve as blueprints for individual training sessions and include 
pre-configured exercises, sets, and targets.

Application Context:
Core feature module for the Content Library and Marketplace sections.
Interacts with 'training_templates' and 'template_exercises' tables.

Data Flow:
User/Trainer -> feature_training_templates.py -> Supabase DB (Templates & Exercises)
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List

from dependencies import get_current_user
from database import get_supabase
from supabase import Client
from features.schemas_training import (
    TrainingTemplateCreate, TrainingTemplateResponse,
    TemplateExerciseCreate, TemplateExerciseResponse
)
from features.utils_hashing import generate_training_hash

router = APIRouter()

@router.post("/", response_model=TrainingTemplateResponse)
def create_training_template(
    template_data: TrainingTemplateCreate, 
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Create a new training template (reusable plan).
    
    Args:
        template_data (TrainingTemplateCreate): The template metadata (title, visibility, etc).
        current_user (dict): The authenticated owner/creator.
        supabase (Client): Injected Supabase client.
        
    Returns:
        TrainingTemplateResponse: The newly created template record.
        
    Side Effects:
        - Inserts a record into the 'training_templates' table.
    """
    try:
        data_to_insert = template_data.model_dump()
        # Ensure the template is linked to the authenticated user if not already provided (e.g. from copy).
        data_to_insert["owner_id"] = template_data.owner_id or current_user.get("id")
        
        response = supabase.table("training_templates").insert(data_to_insert).execute()
        if not response.data:
            raise Exception("Failed to create template")
            
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create training template: {str(e)}")

@router.get("/", response_model=List[TrainingTemplateResponse])
def list_training_templates(
    include_exercises: bool = False,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Retrieve training templates accessible to the current user (owned by them).
    
    Args:
        include_exercises (bool): Whether to include full exercise details and content hash.
        current_user (dict): The authenticated user.
        supabase (Client): Injected Supabase client.
        
    Returns:
        List[TrainingTemplateResponse]: A list of templates owned by the user.
    """
    try:
        # Optimization: Only join with exercises if requested (avoids timeout for simple lists)
        select_string = "*, owner:users!owner_id(first_name, last_name, email, username)"
        if include_exercises:
            select_string += ", exercises:template_exercises(*)"

        response = supabase.table("training_templates") \
            .select(select_string) \
            .eq("owner_id", current_user.get("id")) \
            .execute()
        
        templates = response.data or []
        if include_exercises:
            for t in templates:
                exs = t.get("exercises", [])
                t["content_hash"] = generate_training_hash(t.get("title"), t.get("description"), exs)
            
        return templates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch training templates: {str(e)}")

@router.get("/{template_id}")
def get_training_template(
    template_id: str, 
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Retrieve full details of a specific training template including its exercises.
    
    Args:
        template_id (str): The UUID of the template.
        current_user (dict): The authenticated user.
        supabase (Client): Injected Supabase client.
        
    Returns:
        dict: Template metadata with an 'exercises' list attached.
        
    Raises:
        HTTPException: 404 if the template is not found.
    """
    try:
        # Fetch the main template metadata with owner info.
        template = supabase.table("training_templates") \
            .select("*, owner:users!owner_id(first_name, last_name, email, username)") \
            .eq("id", template_id) \
            .single() \
            .execute()
        if not template.data:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Fetch ordered exercises for this specific template blueprint.
        exercises = supabase.table("template_exercises").select("*").eq("template_id", template_id).order("order_index").execute()
        
        result = template.data
        result["exercises"] = exercises.data
        result["content_hash"] = generate_training_hash(result.get("title"), result.get("description"), exercises.data)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch training template: {str(e)}")

@router.post("/{template_id}/exercises", response_model=TemplateExerciseResponse)
def add_template_exercise(
    template_id: str, 
    exercise_data: TemplateExerciseCreate, 
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Add a specific exercise configuration (snapshot) to a template blueprint.
    
    Args:
        template_id (str): The target template.
        exercise_data (TemplateExerciseCreate): The exercise targets (reps, sets, etc).
        current_user (dict): Authenticated user.
        supabase (Client): Injected Supabase client.
        
    Returns:
        TemplateExerciseResponse: The newly added exercise configuration.
        
    Side Effects:
        - Inserts a record into 'template_exercises'.
    """
    try:
        # Verify ownership: Only the owner should be able to modify the blueprint.
        template = supabase.table("training_templates").select("owner_id").eq("id", template_id).single().execute()
        if not template.data or template.data.get("owner_id") != current_user.get("id"):
            raise HTTPException(status_code=403, detail="Not authorized to modify this template")

        data_to_insert = exercise_data.model_dump()
        data_to_insert["template_id"] = template_id
        
        response = supabase.table("template_exercises").insert(data_to_insert).execute()
        if not response.data:
            raise Exception("Failed to insert template exercise")
            
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add template exercise: {str(e)}")

@router.post("/{template_id}/adopt", response_model=TrainingTemplateResponse)
def adopt_template(
    template_id: str, 
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Adopt (clone) a training template from the marketplace into the user's personal library.
    
    Args:
        template_id (str): The ID of the template to adopt.
        current_user (dict): The authenticated user.
        supabase (Client): Injected Supabase client.
        
    Returns:
        TrainingTemplateResponse: The newly created personal template copy.
    """
    try:
        # 1. Fetch source template
        source = supabase.table("training_templates").select("*").eq("id", template_id).single().execute()
        if not source.data:
            raise HTTPException(status_code=404, detail="Template not found")
        
        s_data = source.data
        
        # 2. Create new template copy
        new_template_payload = {
            "title": s_data.get("title"),
            "description": s_data.get("description"),
            "sport": s_data.get("sport"),
            "difficulty": s_data.get("difficulty"),
            "image_url": s_data.get("image_url"),
            "visibility": "private",
            "owner_id": current_user.get("id")
        }
        
        new_template_res = supabase.table("training_templates").insert(new_template_payload).execute()
        if not new_template_res.data:
            raise Exception("Failed to create template copy")
            
        new_template = new_template_res.data[0]
        new_id = new_template["id"]
        
        # 3. Fetch and copy template exercises
        exercises = supabase.table("template_exercises").select("*").eq("template_id", template_id).execute()
        if exercises.data:
            new_exercises_payload = []
            for ex in exercises.data:
                ex_copy = dict(ex)
                ex_copy.pop("id", None)
                ex_copy.pop("created_at", None)
                ex_copy["template_id"] = new_id
                new_exercises_payload.append(ex_copy)
                
            supabase.table("template_exercises").insert(new_exercises_payload).execute()
            
        return new_template
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to adopt template: {str(e)}")

