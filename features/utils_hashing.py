import hashlib
import json
from typing import List, Dict, Any

def generate_training_hash(title: str, description: str, exercises: List[Dict[str, Any]]) -> str:
    """
    Generates a SHA-256 hash of the training content.
    Identical content (title, desc, exercises) will yield the same hash.
    """
    # Normalize and sort exercises to ensure consistent hashing
    # Ensure title and description are strings
    safe_title = str(title or "").strip()
    safe_description = str(description or "").strip()
    
    normalized_exercises = []
    for ex in exercises:
        normalized_exercises.append({
            "name": ex.get("custom_name") or ex.get("name") or "",
            "desc": ex.get("custom_description") or "",
            "sets": ex.get("target_sets") or 0,
            "reps": str(ex.get("target_reps") or ""),
            "weight": float(ex.get("target_weight") or 0),
            "duration": int(ex.get("target_duration_seconds") or 0)
        })
    
    # Sort by order_index if available, otherwise name-based sorting (though order matters)
    # Usually exercises have order_index in the DB
    
    payload = {
        "title": safe_title,
        "description": safe_description,
        "exercises": normalized_exercises
    }
    
    payload_str = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(payload_str.encode()).hexdigest()
