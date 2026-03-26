"""
SportyFY - Marketplace Feature

Purpose:
This module provides endpoints for browsing, creating, and ordering items 
in the SportyFY marketplace. It handles the lifecycle of marketplace 
listings and transactions.

Application Context:
Core feature module for the Marketplace section of the app.
Interacts with 'marketplace_items' and 'marketplace_orders' tables.

Data Flow:
Creator/Buyer -> feature_marketplace.py -> Supabase DB (Marketplace)
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List

from dependencies import get_current_user, require_role
from database import get_supabase
from supabase import Client

router = APIRouter()

@router.get("/")
def list_marketplace_items(supabase: Client = Depends(get_supabase)):
    """
    Retrieve a list of all available marketplace items.
    
    Args:
        supabase (Client): Injected Supabase client.
        
    Returns:
        List[dict]: A list of marketplace item records.
    """
    try:
        response = supabase.table("marketplace_items").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch marketplace items: {str(e)}")

@router.get("/{item_id}")
def get_marketplace_item(item_id: str, supabase: Client = Depends(get_supabase)):
    """
    Retrieve detailed information for a specific marketplace item.
    
    Args:
        item_id (str): The UUID of the marketplace item.
        supabase (Client): Injected Supabase client.
        
    Returns:
        dict: Detailed item metadata.
        
    Raises:
        HTTPException: 404 if the item is not found.
    """
    try:
        response = supabase.table("marketplace_items").select("*").eq("id", item_id).single().execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Item not found")
        return response.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch marketplace item: {str(e)}")

@router.post("/")
def create_marketplace_item(
    item: dict, 
    user: dict = Depends(require_role(["creator", "platform_admin"])),
    supabase: Client = Depends(get_supabase)
):
    """
    Create a new marketplace item listing.
    
    Args:
        item (dict): The item metadata (title, price, category, etc).
        user (dict): The authenticated user with 'creator' or 'platform_admin' role.
        
    Returns:
        dict: Confirmation message and the created item data.
        
    Side Effects:
        - Inserts a record into the 'marketplace_items' table.
    """
    try:
        # Automatically link the item to the authenticated creator.
        item["creator_auth_id"] = user.get("id")
        response = supabase.table("marketplace_items").insert(item).execute()
        return {"message": "Marketplace item created successfully", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create marketplace item: {str(e)}")

@router.post("/orders")
def create_order(
    order: dict, 
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Create a purchase order for a marketplace item.
    
    Args:
        order (dict): Order details (item_id, quantity, etc).
        current_user (dict): The authenticated buyer.
        
    Returns:
        dict: Confirmation message and the created order record.
        
    Side Effects:
        - Inserts a record into the 'marketplace_orders' table.
    """
    try:
        # Automatically link the order to the authenticated buyer.
        order["buyer_auth_id"] = current_user.get("id")
        response = supabase.table("marketplace_orders").insert(order).execute()
        return {"message": "Order created successfully", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")

