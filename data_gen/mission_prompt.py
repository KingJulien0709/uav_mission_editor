from .mission_gen_object import MissionType

PROMPT_HEADER = """
**System Role:**
You are a Synthetic Data Generator for Autonomous Drone Navigation.
Generate a `Mission` with exactly {{N}} `Waypoint` candidates.

**Global Navigation Rule (CRITICAL):**
1. **Subject = Building:** The `subject_description` for every Forward Image MUST describe a specific **House** or **Building Facade**. Do not describe just a door or a sign.
2. **House Number Anchor:** The House Number must be described as being **mounted on** that specific building.

**Output Rules:**
1. Return purely JSON.
2. Exactly ONE `is_target=True`.
3. {{N-1}} Distractors.
"""

LOGIC_LOCATE_AND_TRACK = """
**Mission Profile: LOCATE_AND_TRACK**
- **Instruction:** "Track [Person] near House Number [Number]."
- **Target Waypoint Logic:**
    - **Forward Image:**
        - `subject_description`: "A modern beige stucco house with a flat roof"
        - `landmarks`: 
            - HOUSE_NUMBER: "42", "Black metal numbers mounted next to the garage"
            - HUMAN: "Person in blue jacket", "Walking on the sidewalk in front of the house"
"""

LOGIC_LOCATE_AND_LAND_SAFELY = """
**Mission Profile: LOCATE_AND_LAND_SAFELY**
- **Instruction:** "Land near [Object] at House Number [Number]."
- **Target Waypoint Logic:**
    - **Forward Image:**
        - `subject_description`: "A classic red brick cottage with a white porch"
        - `landmarks`:
            - HOUSE_NUMBER: "12", "White painted wood numbers on the porch column"
            - OBSTACLE: "Green Trashcan", "Placed near the porch steps"
"""

LOGIC_LOCATE_AND_REPORT = """
**Mission Profile: LOCATE_AND_REPORT**
- **Instruction:** "Report detail at House Number [Number]."
- **Target Waypoint Logic:**
    - **Forward Image:**
        - `subject_description`: "A large warehouse building with corrugated metal siding"
        - `landmarks`:
            - HOUSE_NUMBER: "405", "Large industrial font painted directly on the metal siding"
"""

PROMPT_FOOTER = """
**Generation Steps:**
1. **Define the House:** Create a distinct architectural style for the Target (e.g., "Tudor style", "Modern glass").
2. **Attach the Number:** Ensure the House Number visual attributes describe *how* it is attached to that specific house style.
3. **Consistency:** If the instruction says "Red House", the `subject_description` MUST start with "A red house...".

**Generate the Mission JSON now.**
"""

def build_meta_prompt(mission_type_str: str, n_waypoints: int) -> str:
    try:
        mission_type = MissionType(mission_type_str)
    except ValueError:
        raise ValueError(f"Unknown Mission Type: {mission_type_str}")

    if mission_type == MissionType.LOCATE_AND_TRACK:
        logic_module = LOGIC_LOCATE_AND_TRACK
    elif mission_type == MissionType.LOCATE_AND_LAND_SAFELY:
        logic_module = LOGIC_LOCATE_AND_LAND_SAFELY
    elif mission_type == MissionType.LOCATE_AND_REPORT:
        logic_module = LOGIC_LOCATE_AND_REPORT
    else:
        raise ValueError(f"Logic not implemented for: {mission_type}")

    full_prompt = f"{PROMPT_HEADER}\n\n{logic_module}\n\n{PROMPT_FOOTER}"
    final_prompt = full_prompt.replace("{{N}}", str(n_waypoints))
    
    return final_prompt