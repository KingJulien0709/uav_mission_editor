from utils.data_utils import validate_data_structure

def test_validate_data_structure_correct():
    data = [
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
    assert validate_data_structure(data) is True

def test_validate_data_structure_missing_field():
    data = [
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
    assert validate_data_structure(data) is False
