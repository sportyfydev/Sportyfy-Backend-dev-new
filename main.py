"""
SportyFY - API Entry Point & Showcase Hub

Purpose:
This module serves as the primary entry point for the SportyFY FastAPI backend.
It initializes the FastAPI application, configures CORS, and aggregates all 
feature-specific routers.

Application Context:
The "Heart" of the backend. It also contains example/showcase endpoints that 
demonstrate the functionality of the decoupled feature modules.

Data Flow:
Client Request -> main.py (Routing) -> feature_*.py (Business Logic) -> Response
"""

import logging
import traceback
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List

# Import feature routers (Decoupled Logic)
from features.feature_training_ai import router as training_ai_router
from features.feature_content_library import router as content_library_router
from features.feature_marketplace import router as marketplace_router
from features.feature_training_sessions import router as training_sessions_router
from features.feature_training_templates import router as training_templates_router
from features.feature_kpi_tracking import router as kpi_tracking_router
from features.feature_kpis import router as kpis_router
from features.feature_metrics import router as metrics_router
from features.feature_users import router as users_router
from features.feature_uploads import router as uploads_router

# Import core dependencies and DB helpers
from dependencies import get_current_user, require_role
from database import get_supabase

# Configure Logging to file
logging.basicConfig(level=logging.INFO, filename="debug_info.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize the FastAPI application
app = FastAPI(
    title="SportyFY API",
    description="Backend API for the SportyFY Multisport Platform",
    version="1.0.0",
)

@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        tb = traceback.format_exc()
        logging.error(f"500 Internal Server Error at {request.url.path}: {str(e)}\n{tb}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error. Please check the logs."}
        )

# Configure CORS (Cross-Origin Resource Sharing)
import os
default_origins = [
    "http://localhost:5173",
    "https://sportyfy-frontend-0yth.onrender.com", # Aktuelles Frontend
    "https://sportyfy-frontend-du2z.onrender.com"  # Altes/Alternatives Frontend
]
allowed_origins_str = os.environ.get("ALLOWED_ORIGINS", "")
if allowed_origins_str:
    allowed_origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]
else:
    allowed_origins = default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Feature Router Registration ---
# Each router is prefixed according to its domain to maintain a clean API structure.
app.include_router(training_ai_router, prefix="/api/v1/training-ai", tags=["Training AI"])
app.include_router(content_library_router, prefix="/api/v1/content", tags=["Content Library"])
app.include_router(marketplace_router, prefix="/api/v1/marketplace", tags=["Marketplace"])
app.include_router(training_templates_router, prefix="/api/v1/templates", tags=["Training Templates"])
app.include_router(training_sessions_router, prefix="/api/v1/sessions", tags=["Training Sessions"])
app.include_router(kpis_router, prefix="/api/v1/kpis", tags=["KPIs"])
app.include_router(kpi_tracking_router, prefix="/api/v1/kpi", tags=["KPI Tracking"])
app.include_router(metrics_router, prefix="/api/v1", tags=["User Metrics & Goals"])
app.include_router(users_router, prefix="/api/v1/users", tags=["User Management"])
app.include_router(uploads_router, prefix="/api/v1/uploads", tags=["Uploads"])


@app.get("/health", tags=["System"])
def health_check():
    """
    Simple health check endpoint to verify that the API server is up and running.
    
    Returns:
        dict: Status and descriptive message.
    """
    return {"status": "ok", "message": "SportyFY API is operational"}

@app.get("/api/v1/db-test", tags=["System"])
def test_db_connection():
    """
    Connectivity test for Supabase integration.
    Does not require authentication.
    
    Returns:
        dict: Success status or raises 500 HTTPException on failure.
        
    Side Effects:
        - Performs a live API request to the Supabase database.
    """
    try:
        client = get_supabase()
        # Ping the DB by fetching 1 row from feature flags (common heartbeat table)
        client.table("feature_flags").select("*").limit(1).execute()
        return {"status": "success", "message": "Successfully connected to Supabase Database!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

@app.get("/api/v1/me", tags=["Auth"])
def get_my_profile(current_user: dict = Depends(get_current_user)):
    """
    Identity endpoint for the currently authenticated user.
    
    Args:
        current_user (dict): Injected user data from get_current_user dependency.
        
    Returns:
        dict: User ID and email extracted from the JWT.
    """
    return {
        "message": "Authentication successful",
        "user_id": current_user.get("id"),
        "email": current_user.get("email"),
        "avatar_url": current_user.get("user_metadata", {}).get("avatar_url") or current_user.get("avatar_url")
    }

@app.get("/api/v1/admin-only", tags=["System"])
def test_admin_role(user: dict = Depends(require_role(["platform_admin"]))):
    """
    Restricted endpoint requiring the 'platform_admin' role.
    
    Args:
        user (dict): Injected user data (only if role check passes).
        
    Returns:
        dict: Welcome message for the admin.
    """
    return {"message": "Welcome Admin!"}

# --- Showcase / Example Endpoints ---
# These endpoints describe the functionality of the feature modules.
# As per Global Rules, they serve to document and demonstrate API usage.

@app.get("/api/v1/example-marketplace", tags=["Examples"])
def example_feature_marketplace():
    """
    Demonstrates the marketplace module capabilities.
    """
    return {
        "message": "Marketplace functionality is available at /api/v1/marketplace",
        "example_routes": [
            "GET /api/v1/marketplace/ - List items",
            "POST /api/v1/marketplace/ - Create item",
        ]
    }

@app.get("/api/v1/example-training-sessions", tags=["Examples"])
def example_feature_training_sessions():
    """
    Demonstrates the training sessions (workout tracking) module capabilities.
    """
    return {
        "message": "Training Sessions functionality is available at /api/v1/sessions",
        "example_routes": [
            "POST /api/v1/sessions/exercises/{id}/logs - Log a set",
        ]
    }

@app.get("/api/v1/example-training-templates", tags=["Examples"])
def example_feature_training_templates():
    """
    Demonstrates the training templates (workout plans) module capabilities.
    """
    return {
        "message": "Training Templates functionality is available at /api/v1/templates",
        "example_routes": [
            "POST /api/v1/templates/ - Create template",
            "POST /api/v1/templates/{id}/exercises - Add exercise to template",
            "POST /api/v1/sessions/instantiate/{template_id} - Create session from template"
        ]
    }

@app.get("/api/v1/example-kpi-tracking", tags=["Examples"])
def example_feature_kpi_tracking():
    """
    Demonstrates the automated KPI tracking module capabilities.
    """
    return {
        "message": "KPI Tracking functionality is available at /api/v1/kpi",
        "example_routes": [
            "GET /api/v1/kpi/summary - Get total volume & workouts",
            "GET /api/v1/kpi/exercise/{id} - Get exercise progression history"
        ]
    }

@app.get("/api/v1/example-users", tags=["Examples"])
def example_feature_users():
    """
    Demonstrates the identity and account management module capabilities.
    """
    return {
        "message": "User Management functionality is available at /api/v1/users",
        "example_routes": [
            "DELETE /api/v1/users/me - Delete own account permanently"
        ]
    }

def showcase_hub():
    """
    Showcase entry point that prints example API responses to the console.
    Fulfills the 'Main Showcase Hub' requirement.
    """
    print("SportyFY Backend - Showcasing Examples")
    print("-" * 40)
    print("Marketplace Example Output:")
    print(example_feature_marketplace())
    print("-" * 40)
    print("Training Sessions Example Output:")
    print(example_feature_training_sessions())
    print("-" * 40)
    print("Training Templates Example Output:")
    print(example_feature_training_templates())
    print("-" * 40)
    print("KPI Tracking Example Output:")
    print(example_feature_kpi_tracking())
    print("-" * 40)
    print("User Management Example Output:")
    print(example_feature_users())
    print("-" * 40)

if __name__ == "__main__":
    # When running main.py directly, trigger the showcase hub.
    showcase_hub()

