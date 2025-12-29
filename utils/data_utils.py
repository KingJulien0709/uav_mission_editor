import json
import os
import shutil
from typing import List, Dict, Any, Optional

PROJECTS_DIR = "projects"

def list_projects() -> List[str]:
    """Returns a list of project names."""
    if not os.path.exists(PROJECTS_DIR):
        return []
    return [d for d in os.listdir(PROJECTS_DIR) if os.path.isdir(os.path.join(PROJECTS_DIR, d))]

def create_project(project_name: str) -> bool:
    """Creates a new project directory structure. Returns True if successful, False if already exists."""
    project_path = os.path.join(PROJECTS_DIR, project_name)
    if os.path.exists(project_path):
        return False
    
    os.makedirs(os.path.join(project_path, "images"), exist_ok=True)
    metadata_path = os.path.join(project_path, "metadata.json")
    
    # Initialize with empty missions structure
    initial_data = {
        "missions": []
    }
    
    with open(metadata_path, 'w') as f:
        json.dump(initial_data, f, indent=4)
        
    return True

def get_project_path(project_name: str) -> str:
    return os.path.join(PROJECTS_DIR, project_name)

def load_project_data(project_name: str) -> Dict[str, Any]:
    project_path = get_project_path(project_name)
    metadata_path = os.path.join(project_path, "metadata.json")
    
    if not os.path.exists(metadata_path):
        return {"missions": []}
        
    with open(metadata_path, 'r') as f:
        data = json.load(f)
        
    # Migration: If it's the old format with top-level "waypoints", move them to a default mission
    if "waypoints" in data and "missions" not in data:
        legacy_mission = {
            "id": "default_mission",
            "name": "Default Mission",
            "type": "locate_and_report", 
            "instruction": data.get("instruction", ""),
            "waypoints": data["waypoints"]
        }
        data = {"missions": [legacy_mission]}
        # We don't verify save here, we just return the migrated structure. 
        # It will be saved on next user save action.
        
    return data

def save_project_data(project_name: str, data: Dict[str, Any]):
    project_path = get_project_path(project_name)
    metadata_path = os.path.join(project_path, "metadata.json")
    
    # Ensure directory exists (just in case)
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    
    with open(metadata_path, 'w') as f:
        json.dump(data, f, indent=4)

# Legacy Global Dataset Functions (Deprecated but kept for safety if needed)
def load_dataset(metadata_path: str) -> List[Dict[str, Any]]:
    # Legacy support
    if not os.path.exists(metadata_path):
        return []
    with open(metadata_path, 'r') as f:
        return json.load(f)

def save_dataset(metadata_path: str, data: List[Dict[str, Any]]):
    # Legacy support
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    with open(metadata_path, 'w') as f:
        json.dump(data, f, indent=4)

def validate_data_structure(data: Any) -> bool:
    # Adjusted validation for { missions: [...] }
    if not isinstance(data, dict): 
        return False
    
    if "missions" in data:
        for m in data["missions"]:
            if "waypoints" not in m: return False
            for wp in m["waypoints"]:
                 if not all(k in wp for k in ("id", "gt_entities", "is_target", "media")):
                     return False
        return True
    
    return False
