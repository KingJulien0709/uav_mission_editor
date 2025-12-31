import json
import os
import glob
import yaml
from typing import Dict, Any, List

MISSION_TYPES_DIR = "configs/mission_types"


class LiteralScalarString(str):
    """A string that will be represented as a literal block scalar in YAML."""
    pass


class CustomDumper(yaml.SafeDumper):
    """Custom YAML dumper that uses literal block scalar style for multiline strings."""
    pass


def str_representer(dumper, data):
    """Represent strings, using literal block style for multiline."""
    if '\n' in data:
        # Strip trailing whitespace from each line to allow literal block style
        # YAML doesn't support trailing spaces in literal block scalars
        lines = data.split('\n')
        cleaned_lines = [line.rstrip() for line in lines]
        cleaned_data = '\n'.join(cleaned_lines)
        # Use literal block scalar style (|) for multiline strings
        return dumper.represent_scalar('tag:yaml.org,2002:str', cleaned_data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


# Register the custom representer
CustomDumper.add_representer(str, str_representer)

DEFAULT_MISSION_TYPES = {
    "locate_and_report": {
        "description": "Locate the target and report its position.",
        "default_state": {"zoom_level": 1, "report_format": "standard"}
    },
    "locate_and_land_safely": {
        "description": "Locate the target and perform a safe landing procedure.",
        "default_state": {"landing_zone_radius": 5, "safety_check": True}
    },
    "locate_and_track": {
        "description": "Locate the target and maintain tracking.",
        "default_state": {
            "initial_state": "execution",
            "image_resolution": {
                "width": 640,
                "height": 480
            },
            "states": {
                "execution": {
                    "prompt": "You are a **UAV controller** executing a multi-step task plan...\n",
                    "output_keys": [
                        {"justification": {"type": "string", "max_length": 300}},
                        {"tool_call": {"type": "object"}},
                        {"information": {"type": "string", "max_length": 300}}
                    ],
                    "observations": ["current_location", "locations_to_be_visited", "past_locations", "plan"],
                    "tools": ["next_goal"],
                    "verifiers": [{"formatted_verifier": {"reward_factor": 1.0}}],
                    "state_transitions": {
                        "conditions": [
                            {"condition": "{next_goal} == 'ground'", "next_state": "conclusion_generation"},
                            {"condition": "{locations_to_be_visited} == []", "next_state": "conclusion_generation"},
                            {"condition": "else", "next_state": "execution"}
                        ],
                        "error": {"next_state": "error"}
                    }
                },
                "conclusion_generation": {
                    "prompt": "You are the **UAV controller** responsible for providing the final answer...\n",
                    "output_keys": [{"justification": "string"}, {"tool_call": "object"}],
                    "tools": ["report_final_conclusion"],
                    "state_transitions": {"conditions": [{"condition": "True", "next_state": "end"}]}
                }
            }
        }
    }
}

def load_mission_types() -> Dict[str, Any]:
    if not os.path.exists(MISSION_TYPES_DIR):
        os.makedirs(MISSION_TYPES_DIR, exist_ok=True)
        # Initialize with defaults if empty
        for name, config in DEFAULT_MISSION_TYPES.items():
            save_mission_type(name, config)
        return DEFAULT_MISSION_TYPES

    mission_types = {}
    # Find all json and yaml/yml files
    config_files = glob.glob(os.path.join(MISSION_TYPES_DIR, "*.json")) + \
                   glob.glob(os.path.join(MISSION_TYPES_DIR, "*.yaml")) + \
                   glob.glob(os.path.join(MISSION_TYPES_DIR, "*.yml"))
    
    if not config_files:
        # Fallback to defaults and save them as JSON by default
        for name, config in DEFAULT_MISSION_TYPES.items():
            save_mission_type(name, config)
        return DEFAULT_MISSION_TYPES

    # Process files, preferring YAML if both exist for the same name
    found_files = {}
    for file_path in config_files:
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        ext = os.path.splitext(file_path)[1].lower()
        if base_name not in found_files or ext in ['.yaml', '.yml']:
            found_files[base_name] = file_path

    for name, file_path in found_files.items():
        try:
            with open(file_path, 'r') as f:
                if file_path.endswith(('.yaml', '.yml')):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
                
                # Check if it's nested (has description/default_state) or flat
                if isinstance(data, dict) and ("default_state" in data or "description" in data):
                    mission_types[name] = data
                else:
                    # Treat as flat: the whole object is the default_state
                    mission_types[name] = {
                        "description": name.replace('_', ' ').title(),
                        "default_state": data
                    }
        except (json.JSONDecodeError, yaml.YAMLError, IOError):
            continue
            
    return mission_types

def save_mission_type(name: str, config: Dict[str, Any], prefer_yaml: bool = False):
    os.makedirs(MISSION_TYPES_DIR, exist_ok=True)
    
    # Check if a file already exists to preserve format
    json_path = os.path.join(MISSION_TYPES_DIR, f"{name}.json")
    yaml_path = os.path.join(MISSION_TYPES_DIR, f"{name}.yaml")
    
    # Remove ui_metadata before saving (it's editor-only data, not part of the config)
    config_to_save = {k: v for k, v in config.items() if k != 'ui_metadata'}
    
    if os.path.exists(yaml_path) or prefer_yaml:
        with open(yaml_path, 'w') as f:
            yaml.dump(config_to_save, f, Dumper=CustomDumper, default_flow_style=False, 
                     sort_keys=False, allow_unicode=True, width=1000)
        # Delete JSON if it exists to avoid confusion
        if os.path.exists(json_path):
            os.remove(json_path)
    else:
        with open(json_path, 'w') as f:
            json.dump(config_to_save, f, indent=4)

def save_mission_types(types_config: Dict[str, Any]):
    """Saves all mission types, deleting files for keys not in types_config."""
    os.makedirs(MISSION_TYPES_DIR, exist_ok=True)
    
    # Current files
    existing_files = glob.glob(os.path.join(MISSION_TYPES_DIR, "*.json")) + \
                     glob.glob(os.path.join(MISSION_TYPES_DIR, "*.yaml")) + \
                     glob.glob(os.path.join(MISSION_TYPES_DIR, "*.yml"))
    existing_names = [os.path.splitext(os.path.basename(f))[0] for f in existing_files]
    
    # Save/Update (preserves existing format)
    for name, config in types_config.items():
        save_mission_type(name, config)
        
    # Delete removed types
    for name in set(existing_names):
        if name not in types_config:
            # Delete both possible extensions
            for ext in ['.json', '.yaml', '.yml']:
                file_path = os.path.join(MISSION_TYPES_DIR, f"{name}{ext}")
                if os.path.exists(file_path):
                    os.remove(file_path)

def get_mission_type_names() -> List[str]:
    return list(load_mission_types().keys())


def delete_mission_type(name: str) -> bool:
    """Delete a mission type by name. Returns True if deleted, False if not found."""
    deleted = False
    for ext in ['.json', '.yaml', '.yml']:
        file_path = os.path.join(MISSION_TYPES_DIR, f"{name}{ext}")
        if os.path.exists(file_path):
            os.remove(file_path)
            deleted = True
    return deleted

