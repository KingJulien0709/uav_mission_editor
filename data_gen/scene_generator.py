from google import genai
from google.genai import types

import time
from google.genai.errors import ServerError
from .mission_gen_object import MissionType, Mission
from .mission_prompt import build_meta_prompt

class SceneGenerator:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-lite"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate_scene(self, mission_type_str: str, waypoints_per_mission: int) -> str:
        prompt = build_meta_prompt(mission_type_str, waypoints_per_mission)
        
        max_retries = 10
        for i in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        thinking_config=types.ThinkingConfig(
                            thinking_budget=10_000,
                            include_thoughts=False
                        ),
                        response_mime_type = "application/json",
                        response_schema=Mission.model_json_schema()
                    )
                )
                return response.text
            except ServerError as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    wait_time = (i + 1) * 5
                    print(f"SceneGenerator: Server overloaded (503). Retrying in {wait_time}s... (Attempt {i+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    raise e
        
        raise ServerError(f"Failed to generate scene after {max_retries} retries due to server overload.")

    

    