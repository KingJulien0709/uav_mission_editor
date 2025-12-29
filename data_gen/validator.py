from pydantic import BaseModel, Field
from typing import List, Optional

from google import genai
from google.genai import types
from google.genai.errors import ServerError

from PIL import Image
import os
import time

class ValidationResult(BaseModel):
    mission_is_valid: bool = Field(..., description="The final verdict. True = Mission is solvable/correct. False = Mission is broken/impossible.")
    confidence_score: float = Field(..., description="Your certainty in the verdict (0.0 to 1.0). 1.0 = Absolutely sure. < 0.8 = Unsure.")
    needs_human_review: bool = Field(..., description="MUST be True if confidence_score is low (< 0.85) or if the image is ambiguous.")
    reasoning: str = Field(..., description="Explanation. E.g., 'Valid (High Confidence): House 42 is clearly legible.'")

class MissionValidator:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-lite", confidence_threshold: float = 0.75):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.confidence_threshold = confidence_threshold

    def load_image(self, relative_path: str, base_dir: str = ".") -> Image.Image:
        path = os.path.join(base_dir, relative_path)
        try:
            return Image.open(path)
        except Exception as e:
            print(f"Error loading image {path}: {e}")
            # Return a placeholder black image to prevent crash, but validation will likely fail
            return Image.new('RGB', (100, 100), color='black')

    def build_validation_prompt(self, mission_entry: dict, image_base_dir: str):
        # Build the validation prompt
        instruction = mission_entry.get('mission_instruction', mission_entry.get('instruction', 'N/A'))
        mission_type = mission_entry['type']
        
        prompt_parts = []
        
        # 1. System Context
        prompt_parts.append(f"""
        **Role:** You are a Quality Assurance Referee for drone missions.
        **Task:** Validate if the generated images match the Mission Instruction.
        
        **Mission Type:** {mission_type}
        **Instruction:** "{instruction}"
        
        **Rule: Low Confidence = Human Review**
        - You must calculate a `confidence_score` (0.0 - 1.0) based on image clarity.
        - **CRITICAL:** If you are not 100% sure (Score < 0.85), you MUST set `needs_human_review` to TRUE.
        - It is better to flag for review than to approve a bad mission.
        
        **Scoring Rubric:**
        - **1.0 (Certain):** Text is sharp, high-contrast, perfectly matches instruction.
        - **0.5 (Uncertain):** Text is blurry, occluded by trees, or ambiguous (e.g. looks like "42" or "4Z").
        - **0.0 (Certain Failure):** House number is definitely missing.
        
        **Analyze the Evidence:**
        """)

        for wp in mission_entry['waypoints']:
            role = "TARGET (Must MATCH)" if wp['is_target'] else "DISTRACTOR (Must FAIL)"
            entity_info = f"Expected Entity: {wp.get('gt_entities', {}).get('house_number', 'N/A')}"
            
            prompt_parts.append(f"\n--- Waypoint {wp['id']} [{role}] ---")
            prompt_parts.append(f"Metadata: {entity_info}")
            
            for label, img_path in wp['media'].items():
                img = self.load_image(img_path, image_base_dir)
                prompt_parts.append(f"Image ({label}):")
                prompt_parts.append(img)

        prompt_parts.append("\n**Final Decision:** Generate the ValidationResult JSON with the fields: mission_is_valid, confidence_score, needs_human_review, reasoning.")
        return prompt_parts

    def validate_mission(self, mission_entry: dict, image_base_dir: str) -> ValidationResult:
        max_retries = 10
        for i in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=self.build_validation_prompt(mission_entry, image_base_dir),
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ValidationResult,
                        thinking_config=types.ThinkingConfig(
                            thinking_budget=5_000,
                        ),
                        temperature=0.1
                    )
                )
                result = response.parsed
                
                # Even if the LLM says "No review needed", we force it if confidence is low.
                if result.confidence_score < self.confidence_threshold:
                    if not result.needs_human_review:
                        result.needs_human_review = True
                        result.reasoning += " [SYSTEM: Forced Review due to Low Confidence]"
                
                return result
            except ServerError as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    wait_time = (i + 1) * 5
                    print(f"MissionValidator: Server overloaded (503). Retrying in {wait_time}s... (Attempt {i+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    raise e
            except Exception as e:
                return ValidationResult(
                    mission_is_valid=False,
                    confidence_score=0.0,
                    needs_human_review=True,
                    reasoning=f"Validator Error: {str(e)}"
                )
        
        return ValidationResult(
            mission_is_valid=False,
            confidence_score=0.0,
            needs_human_review=True,
            reasoning=f"Failed to validate mission after {max_retries} retries due to server overload."
        )




