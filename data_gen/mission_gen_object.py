from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Tuple, Optional

class MissionType(str, Enum):
    LOCATE_AND_TRACK = "locate_and_track"
    LOCATE_AND_LAND_SAFELY = "locate_and_land_safely"
    LOCATE_AND_REPORT = "locate_and_report"

class LandmarkCategory(str, Enum):
    HOUSE_NUMBER = "house_number"
    HUMAN = "human"
    OBSTACLE = "obstacle"
    VEHICLE = "vehicle"
    OTHER = "other"

class Landmark(BaseModel):
    category: LandmarkCategory = Field(..., description="The classification of this object.")
    name: str = Field(..., description="Short identifier, e.g., 'Target House Number'.")
    visual_attributes: str = Field(..., description="Visual details. For numbers: color, font style, placement on wall. HOUSENUMBERS MUST be READABLE.")
    text_content: Optional[str] = Field(None, description="If this is a HOUSE_NUMBER, the exact string to render (e.g., '42').")
    position: List[float] = Field(..., description="Normalized [x, y] coordinates (0.0-1.0).")

class DetailedImagePrompt(BaseModel):
    subject_description: str = Field(..., description="MUST describe the HOUSE or BUILDING structure (e.g., 'A two-story red brick suburban house').")
    environment_context: str = Field(..., description="Surroundings (e.g., 'Green lawn, sunny sky').")
    lighting_and_style: str = Field(..., description="Camera settings (e.g., 'Cinematic drone shot, 4k').")
    landmarks: List[Landmark] = Field(..., description="List of all key objects that MUST appear.")

    @property
    def full_rendering_prompt(self) -> str:
        """
        Constructs a cohesive prompt ensuring the House is the canvas for the Number.
        """
        # 1. Build the Landmark Text Phrases
        landmark_phrases = []
        for l in self.landmarks:
            if l.category == LandmarkCategory.HOUSE_NUMBER and l.text_content:
                # Binds the number to the house facade
                landmark_phrases.append(f"clearly displaying the number '{l.text_content}' which is {l.visual_attributes}")
            else:
                landmark_phrases.append(f"with a {l.name} ({l.visual_attributes}) nearby")

        # 2. Assemble: "A [House] [displaying Number] [with Person nearby]. [Env]. [Light]."
        # This sentence structure forces the House to be the main subject.
        integration_phrase = ", ".join(landmark_phrases)
        
        return f"{self.subject_description}, {integration_phrase}. {self.environment_context}. {self.lighting_and_style}."

class GroundImagePrompt(BaseModel):
    surface_texture: str
    obstacles_and_debris: str
    lighting_angle: str

    @property
    def full_rendering_prompt(self) -> str:
        return f"Top-down drone view looking at {self.surface_texture}. {self.obstacles_and_debris}. {self.lighting_angle}."

class Waypoint(BaseModel):
    forward_image: DetailedImagePrompt
    ground_image: GroundImagePrompt
    secondary_ground_image: Optional[GroundImagePrompt] = None
    ground_is_obstructed: bool
    is_target: bool

class Mission(BaseModel):
    mission_type: MissionType
    mission_instruction: str
    waypoints: List[Waypoint]