import json
import os
from typing import Dict, Any

CONFIG_FILE = "configs/app_config.json"

def load_config() -> Dict[str, str]:
    if not os.path.exists(CONFIG_FILE):
        return {"hf_token": "", "gemini_api_key": ""}
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
         return {"hf_token": "", "gemini_api_key": ""}

def save_config(hf_token: str, gemini_api_key: str):
    config = {"hf_token": hf_token, "gemini_api_key": gemini_api_key}
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
