from data_gen.image_generator import ImageGenerator
from data_gen.scene_generator import SceneGenerator
from data_gen.validator import MissionValidator
from data_gen.mission_gen_object import Mission, Waypoint, MissionType, LandmarkCategory
import time
import uuid
import random
from google.genai.errors import ServerError
from data_gen.validator import ValidationResult
from typing import Optional

class MissionGenPipeline:
    def __init__(self, api_key: str, 
                 instruction_vlm: str = "gemini-2.5-flash-lite",
                 image_generation_model: str ="gemini-2.5-flash-image",
                 verification_vlm: str = "gemini-2.5-flash-lite",
                 waypoints_per_mission: int = 5):
        self.scene_generator = SceneGenerator(api_key, model= instruction_vlm)
        self.image_generator = ImageGenerator(api_key, model= image_generation_model)
        self.validator_model = MissionValidator(api_key, model= verification_vlm)
        self.waypoints_per_mission = waypoints_per_mission

    def generate_waypoint_entry(self, waypoint: Waypoint, mission_id: str, waypoint_id: str) -> dict:
        media_entries = {}
        media_entries['forward_image.png'] = waypoint.forward_image.full_rendering_prompt
        media_entries['ground_image.png'] = waypoint.ground_image.full_rendering_prompt
        if waypoint.secondary_ground_image:
            media_entries['secondary_ground_image.png'] = waypoint.secondary_ground_image.full_rendering_prompt
        output_base_path = f"outputs/{mission_id}/{waypoint_id}"
        for filename, prompt in media_entries.items():
            output_path = f"{output_base_path}/{filename}"
            # Here we assume aspect_ratio and resolution are predefined or passed as parameters
            aspect_ratio = "16:9" if "forward" in filename else "1:1"
            resolution = "2K" if "forward" in filename else "1K"
            #save image automatically
            self.image_generator.generate_image(prompt, output_path, aspect_ratio, resolution)
            
        waypoint_entry = {
            "id": waypoint_id,
            "media": {f"{filename}": f"{output_base_path}/{filename}" for filename in media_entries.keys()},
            "is_target": waypoint.is_target,
            "ground_is_obstructed": waypoint.ground_is_obstructed,
            "landmarks": [landmark.model_dump() for landmark in waypoint.forward_image.landmarks],
            "gt_entities": {
                "house_number": next((l.text_content for l in waypoint.forward_image.landmarks if l.category == LandmarkCategory.HOUSE_NUMBER), "N/A")
            }
        }
        return waypoint_entry


    def generate_mission_entry(self, mission_obj: Mission, dataset_split: str) -> dict:
        # Generate unique mission ID to avoid overwriting images
        unique_id = f"mission_{int(time.time())}_{random.randint(1000, 9999)}"
        
        mission_entry = {
            "id": unique_id,
            "name": "Sample Mission",
            "type": mission_obj.mission_type.value,
            "state_config": {}, # Placeholder for state configuration
            "dataset_split": dataset_split,
            "mission_instruction": mission_obj.mission_instruction,
            "waypoints": []
        }

        for i, waypoint in enumerate(mission_obj.waypoints):
            waypoint_entry = self.generate_waypoint_entry(waypoint, mission_entry["id"], f"waypoint_{i+1:02d}")
            mission_entry["waypoints"].append(waypoint_entry)
                
        return mission_entry

    def run_pipeline(self, mission_type_str: str, dataset_split: str = "sft_train") -> dict:
        try:
            # 1. Generate Mission Scene
            mission_json_str = self.scene_generator.generate_scene(mission_type_str, self.waypoints_per_mission)
            mission_obj = Mission.model_validate_json(mission_json_str)

            # 2. Generate Mission Entry with Images
            mission_entry = self.generate_mission_entry(mission_obj, dataset_split)
            
            validation_result = self.validator_model.validate_mission(mission_entry, image_base_dir=".")

            mission_entry['validation_result'] = validation_result.model_dump()

            return mission_entry
        except ServerError as e:
            print(f"Pipeline failed after retries: {e}")
            return {
                "id": "failed",
                "type": mission_type_str,
                "dataset_split": dataset_split,
                "validation_result": ValidationResult(
                    mission_is_valid=False,
                    confidence_score=0.0,
                    needs_human_review=True,
                    reasoning=f"Mission generation failed after 10 retries due to server overload: {str(e)}"
                ).model_dump()
            }
