import os
import json
import shutil
import tempfile
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download, snapshot_download, create_repo, upload_folder
from typing import Optional, List, Dict, Any, Tuple

# Required fields for a valid mission entry in HuggingFace format
REQUIRED_MISSION_FIELDS = ["instruction", "waypoints", "state_config"]
REQUIRED_WAYPOINT_FIELDS = ["id", "gt_entities", "is_target", "media"]


def validate_hf_mission_format(mission: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate that a mission entry matches the required HuggingFace format.
    This format is compatible with uav_mission_env.MissionEnvironment.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check required mission fields
    for field in REQUIRED_MISSION_FIELDS:
        if field not in mission:
            return False, f"Missing required field: {field}"
    
    # Validate waypoints
    waypoints = mission.get("waypoints", [])
    if not isinstance(waypoints, list):
        return False, "waypoints must be a list"
    
    if len(waypoints) == 0:
        return False, "waypoints list cannot be empty"
    
    for i, wp in enumerate(waypoints):
        for field in REQUIRED_WAYPOINT_FIELDS:
            if field not in wp:
                return False, f"Waypoint {i} missing required field: {field}"
        
        # Validate media field
        media = wp.get("media", [])
        if not isinstance(media, (list, dict)):
            return False, f"Waypoint {i} media must be a list or dict"
    
    # Validate state_config
    state_config = mission.get("state_config", {})
    if not isinstance(state_config, dict):
        return False, "state_config must be a dictionary"
    
    return True, ""


def validate_hf_dataset_format(data: List[Dict[str, Any]]) -> Tuple[bool, str, int]:
    """
    Validate that a dataset matches the required HuggingFace multimodal format.
    Compatible with uav_mission_env for direct environment initialization.
    
    Returns:
        Tuple of (is_valid, error_message, valid_count)
    """
    if not isinstance(data, list):
        return False, "Dataset must be a list of mission entries", 0
    
    valid_count = 0
    for i, mission in enumerate(data):
        is_valid, error = validate_hf_mission_format(mission)
        if not is_valid:
            return False, f"Mission {i}: {error}", valid_count
        valid_count += 1
    
    return True, "", valid_count


def convert_mission_to_hf_format(mission: Dict[str, Any], project_path: str) -> Dict[str, Any]:
    """
    Convert internal mission format to HuggingFace dataset format.
    This format can be directly used with uav_mission_env.MissionEnvironment:
    
    config = {"mission_config": hf_entry}
    env = MissionEnvironment(config=config)
    """
    # Process waypoints: convert media paths to list format for HF compatibility
    hf_waypoints = []
    for wp in mission.get("waypoints", []):
        hf_wp = {
            "id": wp.get("id", ""),
            "gt_entities": wp.get("gt_entities", {}),
            "is_target": wp.get("is_target", False),
        }
        
        # Normalize media to list format for consistency
        media = wp.get("media", [])
        if isinstance(media, dict):
            # Convert dict to list while preserving order
            hf_wp["media"] = list(media.values())
            hf_wp["media_labels"] = list(media.keys())
        else:
            hf_wp["media"] = media if isinstance(media, list) else [media]
        
        hf_waypoints.append(hf_wp)
    
    # Build HF-compatible entry
    hf_entry = {
        # Core mission data (compatible with uav_mission_env)
        "instruction": mission.get("mission_instruction", mission.get("instruction", "")),
        "waypoints": hf_waypoints,
        "state_config": mission.get("state_config", {}),
        
        # Metadata for dataset management
        "id": mission.get("id", ""),
        "name": mission.get("name", ""),
        "type": mission.get("type", "locate_and_report"),
        "dataset_split": mission.get("dataset_split", "sft_train"),
        "creation_source": mission.get("creation_source", "manual"),
    }
    
    return hf_entry


def convert_hf_format_to_mission(hf_entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert HuggingFace dataset format back to internal mission format.
    """
    # Process waypoints: restore media format
    internal_waypoints = []
    for wp in hf_entry.get("waypoints", []):
        internal_wp = {
            "id": wp.get("id", ""),
            "gt_entities": wp.get("gt_entities", {}),
            "is_target": wp.get("is_target", False),
        }
        
        # Restore media format
        media = wp.get("media", [])
        media_labels = wp.get("media_labels", [])
        
        if media_labels and len(media_labels) == len(media):
            # Reconstruct dict format
            internal_wp["media"] = dict(zip(media_labels, media))
        else:
            internal_wp["media"] = media
        
        internal_waypoints.append(internal_wp)
    
    # Build internal mission entry
    internal_entry = {
        "id": hf_entry.get("id", f"imported_{hash(hf_entry.get('instruction', '')) % 10000}"),
        "name": hf_entry.get("name", "Imported Mission"),
        "type": hf_entry.get("type", "locate_and_report"),
        "dataset_split": hf_entry.get("dataset_split", "sft_train"),
        "creation_source": hf_entry.get("creation_source", "imported"),
        "state_config": hf_entry.get("state_config", {}),
        "waypoints": internal_waypoints,
        "instruction": hf_entry.get("instruction", ""),
        "mission_instruction": hf_entry.get("instruction", ""),
    }
    
    return internal_entry


def export_missions_to_hf_dataset(
    missions: List[Dict[str, Any]], 
    project_path: str,
    output_dir: str,
    dataset_name: str
) -> str:
    """
    Export missions to HuggingFace dataset format.
    
    Creates:
    - data/train.json, data/validation.json (split by dataset_split)
    - images/ folder with all mission images
    - README.md with dataset card
    
    Returns path to the created dataset directory.
    """
    dataset_path = os.path.join(output_dir, dataset_name)
    data_path = os.path.join(dataset_path, "data")
    images_path = os.path.join(dataset_path, "images")
    
    os.makedirs(data_path, exist_ok=True)
    os.makedirs(images_path, exist_ok=True)
    
    # Group missions by split
    splits = {"sft_train": [], "rl_train": [], "validation": []}
    
    for mission in missions:
        hf_entry = convert_mission_to_hf_format(mission, project_path)
        split = hf_entry.get("dataset_split", "sft_train")
        if split not in splits:
            split = "sft_train"
        
        # Copy images and update paths
        for wp in hf_entry.get("waypoints", []):
            new_media = []
            for media_path in wp.get("media", []):
                if media_path:
                    # Resolve source path
                    if os.path.isabs(media_path):
                        src_path = media_path
                    else:
                        src_path = os.path.join(project_path, media_path)
                    
                    if os.path.exists(src_path):
                        # Create unique filename
                        filename = f"{hf_entry['id']}_{wp['id']}_{os.path.basename(media_path)}"
                        dest_path = os.path.join(images_path, filename)
                        shutil.copy2(src_path, dest_path)
                        new_media.append(f"images/{filename}")
                    else:
                        new_media.append(media_path)
                else:
                    new_media.append(media_path)
            wp["media"] = new_media
        
        splits[split].append(hf_entry)
    
    # Write split files
    for split_name, split_data in splits.items():
        if split_data:
            split_file = os.path.join(data_path, f"{split_name}.json")
            with open(split_file, "w") as f:
                json.dump(split_data, f, indent=2)
    
    # Create README.md dataset card
    total_missions = sum(len(s) for s in splits.values())
    readme_content = f"""---
license: mit
task_categories:
  - visual-question-answering
  - robotics
language:
  - en
tags:
  - uav
  - mission
  - multimodal
  - vlm
---

# {dataset_name}

UAV Mission Dataset for training and evaluating vision-language models on UAV navigation tasks.

## Dataset Description

This dataset contains **{total_missions}** missions designed for UAV visual navigation and decision-making.

### Splits

| Split | Count |
|-------|-------|
| sft_train | {len(splits['sft_train'])} |
| rl_train | {len(splits['rl_train'])} |
| validation | {len(splits['validation'])} |

## Usage with uav_mission_env

Each entry can be directly used to initialize a `MissionEnvironment`:

```python
from uav_mission_env import MissionEnvironment
import json

# Load a single entry
with open("data/sft_train.json") as f:
    missions = json.load(f)

# Initialize environment with a specific mission
config = {{"mission_config": missions[0]}}
env = MissionEnvironment(config=config)

# Run the mission
obs = env.reset()
action = {{"tool_name": "next_goal", "parameters": {{"next_goal": "waypoint_1"}}}}
obs, reward, terminated, truncated, info = env.step(action)
```

## Data Format

Each mission entry contains:
- `instruction`: The mission goal/instruction
- `waypoints`: List of waypoint dictionaries with:
  - `id`: Unique identifier
  - `gt_entities`: Ground truth entities at this location
  - `is_target`: Whether this is the target location
  - `media`: List of image paths
- `state_config`: State machine configuration for the mission
- `type`: Mission type (e.g., locate_and_report)
- `dataset_split`: Train/validation split

## License

MIT License
"""
    
    readme_path = os.path.join(dataset_path, "README.md")
    with open(readme_path, "w") as f:
        f.write(readme_content)
    
    return dataset_path


def upload_dataset_to_hf(
    local_path: str,
    repo_id: str,
    token: Optional[str] = None,
    private: bool = False
) -> str:
    """
    Upload a local dataset folder to HuggingFace Hub.
    
    Returns the URL of the uploaded dataset.
    """
    api = HfApi(token=token)
    
    # Create repo if it doesn't exist
    try:
        api.repo_info(repo_id=repo_id, repo_type="dataset")
    except Exception:
        create_repo(repo_id=repo_id, repo_type="dataset", token=token, private=private)
    
    # Upload the folder
    api.upload_folder(
        folder_path=local_path,
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="Upload UAV mission dataset",
        token=token
    )
    
    return f"https://huggingface.co/datasets/{repo_id}"


def download_dataset_from_hf(
    repo_id: str,
    local_dir: str,
    token: Optional[str] = None
) -> str:
    """
    Download a dataset from HuggingFace Hub.
    
    Returns the path to the downloaded dataset.
    """
    return snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        local_dir=local_dir,
        token=token
    )


def load_hf_dataset_metadata(repo_id: str, token: Optional[str] = None) -> Tuple[bool, str, int]:
    """
    Load and validate a HuggingFace dataset's metadata without downloading all images.
    
    Returns:
        Tuple of (is_valid, error_or_info_message, mission_count)
    """
    try:
        # Download only the JSON files to a temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            api = HfApi(token=token)
            
            # List files in the repo
            files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
            
            # Find data JSON files
            json_files = [f for f in files if f.endswith('.json') and 'data/' in f]
            
            if not json_files:
                # Try root-level JSON files
                json_files = [f for f in files if f.endswith('.json')]
            
            if not json_files:
                return False, "No JSON data files found in dataset", 0
            
            total_missions = 0
            all_missions = []
            
            for json_file in json_files:
                try:
                    local_path = hf_hub_download(
                        repo_id=repo_id,
                        filename=json_file,
                        repo_type="dataset",
                        local_dir=tmpdir,
                        token=token
                    )
                    
                    with open(local_path, 'r') as f:
                        data = json.load(f)
                    
                    if isinstance(data, list):
                        all_missions.extend(data)
                        total_missions += len(data)
                except Exception as e:
                    continue
            
            if total_missions == 0:
                return False, "No missions found in dataset files", 0
            
            # Validate format
            is_valid, error, valid_count = validate_hf_dataset_format(all_missions)
            
            if not is_valid:
                return False, f"Format validation failed: {error}", 0
            
            return True, f"Found {total_missions} valid missions", total_missions
            
    except Exception as e:
        return False, f"Failed to access dataset: {str(e)}", 0


def import_dataset_from_hf(
    repo_id: str,
    project_path: str,
    token: Optional[str] = None
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Import missions from a HuggingFace dataset into a project.
    
    Returns:
        Tuple of (success, message, list_of_missions)
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Download the full dataset
            dataset_path = download_dataset_from_hf(repo_id, tmpdir, token)
            
            # Find and load JSON files
            all_missions = []
            data_dir = os.path.join(dataset_path, "data")
            
            if os.path.exists(data_dir):
                json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
                for jf in json_files:
                    with open(os.path.join(data_dir, jf), 'r') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            all_missions.extend(data)
            else:
                # Try root level
                json_files = [f for f in os.listdir(dataset_path) if f.endswith('.json')]
                for jf in json_files:
                    with open(os.path.join(dataset_path, jf), 'r') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            all_missions.extend(data)
            
            if not all_missions:
                return False, "No missions found in dataset", []
            
            # Convert to internal format and copy images
            internal_missions = []
            images_dest = os.path.join(project_path, "images")
            os.makedirs(images_dest, exist_ok=True)
            
            for hf_entry in all_missions:
                internal = convert_hf_format_to_mission(hf_entry)
                
                # Copy images
                for wp in internal.get("waypoints", []):
                    media = wp.get("media", [])
                    new_media = []
                    
                    if isinstance(media, dict):
                        new_media_dict = {}
                        for label, path in media.items():
                            src_path = os.path.join(dataset_path, path)
                            if os.path.exists(src_path):
                                filename = os.path.basename(path)
                                dest_path = os.path.join(images_dest, filename)
                                shutil.copy2(src_path, dest_path)
                                new_media_dict[label] = f"images/{filename}"
                            else:
                                new_media_dict[label] = path
                        wp["media"] = new_media_dict
                    else:
                        for path in media:
                            src_path = os.path.join(dataset_path, path)
                            if os.path.exists(src_path):
                                filename = os.path.basename(path)
                                dest_path = os.path.join(images_dest, filename)
                                shutil.copy2(src_path, dest_path)
                                new_media.append(f"images/{filename}")
                            else:
                                new_media.append(path)
                        wp["media"] = new_media
                
                internal_missions.append(internal)
            
            return True, f"Successfully loaded {len(internal_missions)} missions", internal_missions
            
    except Exception as e:
        return False, f"Import failed: {str(e)}", []


# Legacy functions for backward compatibility
def sync_from_hf(repo_id: str, local_dir: str, token: Optional[str] = None):
    """Legacy: Clones or pulls a dataset from HF."""
    return download_dataset_from_hf(repo_id, local_dir, token)


def sync_to_hf(repo_id: str, local_dir: str, commit_message: str = "Update dataset via mission editor", token: Optional[str] = None):
    """Legacy: Pushes local dataset to HF."""
    api = HfApi(token=token)
    
    # Ensure repo exists
    try:
        api.repo_info(repo_id=repo_id, repo_type="dataset")
    except Exception:
        create_repo(repo_id=repo_id, repo_type="dataset", token=token)
    
    api.upload_folder(
        folder_path=local_dir,
        repo_id=repo_id,
        repo_type="dataset",
        commit_message=commit_message,
        token=token
    )
