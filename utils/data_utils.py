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


def get_exports_dir() -> str:
    """Get the exports directory path."""
    exports_dir = "exports"
    os.makedirs(exports_dir, exist_ok=True)
    return exports_dir


def filter_missions(
    missions: List[Dict[str, Any]], 
    selected_types: List[str] = None,
    selected_splits: List[str] = None,
    selected_sources: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Filter missions based on type, split, and source criteria.
    """
    filtered = missions
    
    if selected_types is not None:
        filtered = [m for m in filtered if m.get('type', 'locate_and_report') in selected_types]
    
    if selected_splits is not None:
        filtered = [m for m in filtered if m.get('dataset_split', 'sft_train') in selected_splits]
    
    if selected_sources is not None:
        filtered = [m for m in filtered if m.get('creation_source', 'manual') in selected_sources]
    
    return filtered


def prepare_missions_for_export(
    missions: List[Dict[str, Any]],
    project_name: str
) -> List[Dict[str, Any]]:
    """
    Prepare missions for export by ensuring all required fields are present.
    """
    project_path = get_project_path(project_name)
    prepared = []
    
    for m in missions:
        # Ensure all required fields
        prepared_mission = {
            "id": m.get("id", f"mission_{len(prepared)+1}"),
            "name": m.get("name", "Untitled Mission"),
            "type": m.get("type", "locate_and_report"),
            "dataset_split": m.get("dataset_split", "sft_train"),
            "creation_source": m.get("creation_source", "manual"),
            "instruction": m.get("mission_instruction", m.get("instruction", "")),
            "mission_instruction": m.get("mission_instruction", m.get("instruction", "")),
            "state_config": m.get("state_config", {}),
            "waypoints": m.get("waypoints", [])
        }
        prepared.append(prepared_mission)
    
    return prepared
