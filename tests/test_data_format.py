from utils.data_utils import validate_data_structure
from utils.hf_utils import validate_hf_mission_format, validate_hf_dataset_format


def test_validate_data_structure_correct():
    data = {
        "missions": [
            {
                "instruction": "Test mission",
                "waypoints": [
                    {
                        "id": "wp1",
                        "gt_entities": {"color": "red"},
                        "is_target": True,
                        "media": ["images/test.jpg"]
                    }
                ]
            }
        ]
    }
    assert validate_data_structure(data) is True


def test_validate_data_structure_missing_field():
    data = {
        "missions": [
            {
                "instruction": "Test mission",
                "waypoints": [
                    {
                        "id": "wp1",
                        "gt_entities": {"color": "red"},
                        # "is_target" missing
                        "media": ["images/test.jpg"]
                    }
                ]
            }
        ]
    }
    assert validate_data_structure(data) is False


def test_validate_hf_mission_format_correct():
    """Test that a valid HF mission format passes validation."""
    mission = {
        "instruction": "Find the red box",
        "waypoints": [
            {
                "id": "waypoint_1",
                "gt_entities": {"color": "red"},
                "is_target": True,
                "media": ["images/test.jpg"]
            }
        ],
        "state_config": {
            "initial_state": "execution",
            "states": {}
        }
    }
    is_valid, error = validate_hf_mission_format(mission)
    assert is_valid is True
    assert error == ""


def test_validate_hf_mission_format_missing_instruction():
    """Test that missing instruction fails validation."""
    mission = {
        "waypoints": [
            {
                "id": "waypoint_1",
                "gt_entities": {},
                "is_target": False,
                "media": []
            }
        ],
        "state_config": {}
    }
    is_valid, error = validate_hf_mission_format(mission)
    assert is_valid is False
    assert "instruction" in error


def test_validate_hf_mission_format_missing_waypoint_field():
    """Test that missing waypoint fields fail validation."""
    mission = {
        "instruction": "Test",
        "waypoints": [
            {
                "id": "wp1",
                # Missing gt_entities, is_target, media
            }
        ],
        "state_config": {}
    }
    is_valid, error = validate_hf_mission_format(mission)
    assert is_valid is False


def test_validate_hf_dataset_format():
    """Test HF dataset format validation."""
    dataset = [
        {
            "instruction": "Mission 1",
            "waypoints": [
                {"id": "wp1", "gt_entities": {}, "is_target": True, "media": []}
            ],
            "state_config": {}
        },
        {
            "instruction": "Mission 2",
            "waypoints": [
                {"id": "wp1", "gt_entities": {}, "is_target": False, "media": []}
            ],
            "state_config": {}
        }
    ]
    is_valid, error, count = validate_hf_dataset_format(dataset)
    assert is_valid is True
    assert count == 2
