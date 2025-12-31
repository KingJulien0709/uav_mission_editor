"""
Test export/import functionality with images and uav_mission_env compatibility.
"""
import os
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from utils.hf_utils import (
    convert_mission_to_hf_format,
    convert_hf_format_to_mission,
    export_missions_to_hf_dataset,
    validate_hf_mission_format,
    validate_hf_dataset_format,
)
from utils.data_utils import get_project_path, prepare_missions_for_export


# Test fixtures
@pytest.fixture
def sample_project_with_images(tmp_path):
    """Create a sample project with test images."""
    project_path = tmp_path / "test_project"
    images_path = project_path / "images"
    images_path.mkdir(parents=True)
    
    # Create test images (simple 1x1 pixel PNGs)
    test_images = []
    for i, name in enumerate(["forward.png", "ground.png", "secondary.png"]):
        img_path = images_path / name
        # Create a minimal valid PNG file
        # PNG header + IHDR chunk + IDAT chunk + IEND chunk
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D,  # IHDR length
            0x49, 0x48, 0x44, 0x52,  # IHDR type
            0x00, 0x00, 0x00, 0x01,  # width: 1
            0x00, 0x00, 0x00, 0x01,  # height: 1
            0x08, 0x02,              # bit depth: 8, color type: 2 (RGB)
            0x00, 0x00, 0x00,        # compression, filter, interlace
            0x90, 0x77, 0x53, 0xDE,  # CRC
            0x00, 0x00, 0x00, 0x0C,  # IDAT length
            0x49, 0x44, 0x41, 0x54,  # IDAT type
            0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0xFF, 0x00,  # compressed data
            0x05, 0xFE, 0x02, 0xFE,  # CRC (approximate)
            0x00, 0x00, 0x00, 0x00,  # IEND length
            0x49, 0x45, 0x4E, 0x44,  # IEND type
            0xAE, 0x42, 0x60, 0x82,  # CRC
        ])
        img_path.write_bytes(png_data)
        test_images.append(f"images/{name}")
    
    return project_path, test_images


@pytest.fixture
def sample_mission_with_images(sample_project_with_images):
    """Create a sample mission with image references."""
    project_path, test_images = sample_project_with_images
    
    mission = {
        "id": "mission_1",
        "name": "Test Mission",
        "type": "locate_and_report",
        "dataset_split": "sft_train",
        "creation_source": "manual",
        "instruction": "Find the red box and report its location",
        "mission_instruction": "Find the red box and report its location",
        "state_config": {
            "initial_state": "execution",
            "states": {
                "execution": {
                    "prompt": "Execute the mission",
                    "tools": ["next_goal"],
                    "observations": ["current_location"]
                }
            }
        },
        "waypoints": [
            {
                "id": "waypoint_1",
                "gt_entities": {"color": "blue", "shape": "circle"},
                "is_target": False,
                "media": {
                    "forward": test_images[0],
                    "ground": test_images[1]
                }
            },
            {
                "id": "waypoint_2",
                "gt_entities": {"color": "red", "shape": "box"},
                "is_target": True,
                "media": {
                    "forward": test_images[0],
                    "ground": test_images[2]
                }
            }
        ]
    }
    
    return mission, project_path


class TestImagePathHandling:
    """Test image path handling in conversions."""
    
    def test_convert_dict_media_to_hf_format(self, sample_mission_with_images):
        """Test that dict media format is converted to list format for HF."""
        mission, project_path = sample_mission_with_images
        
        hf_entry = convert_mission_to_hf_format(mission, str(project_path))
        
        # Check waypoints have list media
        for wp in hf_entry["waypoints"]:
            assert isinstance(wp["media"], list), "Media should be converted to list"
            assert "media_labels" in wp, "Media labels should be preserved"
            assert isinstance(wp["media_labels"], list)
    
    def test_convert_hf_format_back_to_dict_media(self, sample_mission_with_images):
        """Test that HF format with labels is converted back to dict media."""
        mission, project_path = sample_mission_with_images
        
        # Convert to HF format
        hf_entry = convert_mission_to_hf_format(mission, str(project_path))
        
        # Convert back
        internal = convert_hf_format_to_mission(hf_entry)
        
        # Check media is restored to dict
        for wp in internal["waypoints"]:
            media = wp["media"]
            # Should be dict if labels were present
            assert isinstance(media, dict), "Media should be restored to dict format"
            assert "forward" in media or "ground" in media
    
    def test_list_media_format_preserved(self):
        """Test that list media format is preserved during conversion."""
        mission = {
            "id": "test",
            "instruction": "Test",
            "state_config": {},
            "waypoints": [{
                "id": "wp1",
                "gt_entities": {},
                "is_target": True,
                "media": ["path/to/img1.jpg", "path/to/img2.jpg"]
            }]
        }
        
        hf_entry = convert_mission_to_hf_format(mission, "/tmp")
        internal = convert_hf_format_to_mission(hf_entry)
        
        # Without labels, should remain as list
        assert isinstance(internal["waypoints"][0]["media"], list)


class TestExportWithImages:
    """Test export functionality with actual images."""
    
    def test_export_copies_images(self, sample_mission_with_images, tmp_path):
        """Test that export correctly copies images to output directory."""
        mission, project_path = sample_mission_with_images
        output_dir = tmp_path / "exports"
        output_dir.mkdir()
        
        # Export
        dataset_path = export_missions_to_hf_dataset(
            missions=[mission],
            project_path=str(project_path),
            output_dir=str(output_dir),
            dataset_name="test_dataset"
        )
        
        # Check images directory exists
        images_dir = Path(dataset_path) / "images"
        assert images_dir.exists(), "Images directory should be created"
        
        # Check images were copied
        copied_images = list(images_dir.glob("*.png"))
        assert len(copied_images) > 0, "Images should be copied"
        
        # Check data file references correct paths
        data_file = Path(dataset_path) / "data" / "sft_train.json"
        assert data_file.exists(), "Data file should be created"
        
        with open(data_file) as f:
            exported_data = json.load(f)
        
        # Verify image paths in exported data start with "images/"
        for mission in exported_data:
            for wp in mission["waypoints"]:
                for media_path in wp["media"]:
                    assert media_path.startswith("images/"), f"Path should be relative: {media_path}"
    
    def test_export_creates_valid_structure(self, sample_mission_with_images, tmp_path):
        """Test that exported dataset has valid structure."""
        mission, project_path = sample_mission_with_images
        output_dir = tmp_path / "exports"
        output_dir.mkdir()
        
        dataset_path = export_missions_to_hf_dataset(
            missions=[mission],
            project_path=str(project_path),
            output_dir=str(output_dir),
            dataset_name="test_dataset"
        )
        
        # Check required files exist
        assert (Path(dataset_path) / "README.md").exists()
        assert (Path(dataset_path) / "data").exists()
        assert (Path(dataset_path) / "images").exists()
        
        # Validate exported data format
        data_file = Path(dataset_path) / "data" / "sft_train.json"
        with open(data_file) as f:
            exported_data = json.load(f)
        
        is_valid, error, count = validate_hf_dataset_format(exported_data)
        assert is_valid, f"Exported data should be valid: {error}"


class TestEnvironmentCompatibility:
    """Test compatibility with uav_mission_env."""
    
    def test_exported_format_is_env_compatible(self, sample_mission_with_images, tmp_path):
        """Test that exported mission can be used with MissionEnvironment."""
        mission, project_path = sample_mission_with_images
        output_dir = tmp_path / "exports"
        output_dir.mkdir()
        
        # Export
        dataset_path = export_missions_to_hf_dataset(
            missions=[mission],
            project_path=str(project_path),
            output_dir=str(output_dir),
            dataset_name="test_dataset"
        )
        
        # Load exported data
        data_file = Path(dataset_path) / "data" / "sft_train.json"
        with open(data_file) as f:
            exported_data = json.load(f)
        
        mission_entry = exported_data[0]
        
        # Validate format matches what MissionEnvironment expects
        assert "instruction" in mission_entry
        assert "waypoints" in mission_entry
        assert "state_config" in mission_entry
        
        # Check waypoint format
        for wp in mission_entry["waypoints"]:
            assert "id" in wp
            assert "gt_entities" in wp
            assert "is_target" in wp
            assert "media" in wp
        
        # Try to initialize environment if available
        try:
            from uav_mission_env import MissionEnvironment
            
            # Create config from exported mission
            config = {"mission_config": mission_entry}
            
            # This should not raise an error
            env = MissionEnvironment(config=config)
            
            # Reset should work
            obs = env.reset()
            assert obs is not None
            
            env.close()
            print("✓ Successfully initialized MissionEnvironment with exported data")
            
        except ImportError:
            pytest.skip("uav_mission_env not installed")
        except Exception as e:
            # Check if error is related to package config issues (not our format)
            error_str = str(e)
            if "all_tools.yaml" in error_str or "ParserError" in error_str:
                pytest.skip(f"uav_mission_env package has config issues: {e}")
            # Print helpful error info
            print(f"Environment initialization failed: {e}")
            print(f"Mission config: {json.dumps(mission_entry, indent=2)}")
            raise


class TestRoundTrip:
    """Test full export-import round trip."""
    
    def test_full_roundtrip_preserves_data(self, sample_mission_with_images, tmp_path):
        """Test that export -> import preserves all mission data."""
        original_mission, project_path = sample_mission_with_images
        output_dir = tmp_path / "exports"
        import_project = tmp_path / "import_project"
        output_dir.mkdir()
        import_project.mkdir()
        (import_project / "images").mkdir()
        
        # Export
        dataset_path = export_missions_to_hf_dataset(
            missions=[original_mission],
            project_path=str(project_path),
            output_dir=str(output_dir),
            dataset_name="test_dataset"
        )
        
        # Simulate import by loading and converting back
        data_file = Path(dataset_path) / "data" / "sft_train.json"
        with open(data_file) as f:
            exported_data = json.load(f)
        
        imported_mission = convert_hf_format_to_mission(exported_data[0])
        
        # Verify key fields are preserved
        assert imported_mission["instruction"] == original_mission["instruction"]
        assert imported_mission["type"] == original_mission["type"]
        assert imported_mission["dataset_split"] == original_mission["dataset_split"]
        assert len(imported_mission["waypoints"]) == len(original_mission["waypoints"])
        
        # Check waypoint data
        for orig_wp, imp_wp in zip(original_mission["waypoints"], imported_mission["waypoints"]):
            assert orig_wp["id"] == imp_wp["id"]
            assert orig_wp["is_target"] == imp_wp["is_target"]
            assert orig_wp["gt_entities"] == imp_wp["gt_entities"]


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_media_list(self):
        """Test handling of empty media list."""
        mission = {
            "id": "test",
            "instruction": "Test",
            "state_config": {},
            "waypoints": [{
                "id": "wp1",
                "gt_entities": {},
                "is_target": True,
                "media": []
            }]
        }
        
        hf_entry = convert_mission_to_hf_format(mission, "/tmp")
        is_valid, error = validate_hf_mission_format(hf_entry)
        assert is_valid, f"Empty media should be valid: {error}"
    
    def test_missing_image_file(self, tmp_path):
        """Test handling when image file doesn't exist."""
        project_path = tmp_path / "project"
        project_path.mkdir()
        output_dir = tmp_path / "exports"
        output_dir.mkdir()
        
        mission = {
            "id": "test",
            "name": "Test",
            "type": "locate_and_report",
            "dataset_split": "sft_train",
            "instruction": "Test",
            "state_config": {},
            "waypoints": [{
                "id": "wp1",
                "gt_entities": {},
                "is_target": True,
                "media": ["images/nonexistent.png"]
            }]
        }
        
        # Should not crash, just keep original path
        dataset_path = export_missions_to_hf_dataset(
            missions=[mission],
            project_path=str(project_path),
            output_dir=str(output_dir),
            dataset_name="test"
        )
        
        assert Path(dataset_path).exists()
    
    def test_absolute_path_handling(self, sample_project_with_images, tmp_path):
        """Test handling of absolute image paths."""
        project_path, test_images = sample_project_with_images
        output_dir = tmp_path / "exports"
        output_dir.mkdir()
        
        # Create mission with absolute paths
        abs_image_path = str(project_path / test_images[0])
        mission = {
            "id": "test",
            "name": "Test",
            "type": "locate_and_report",
            "dataset_split": "sft_train",
            "instruction": "Test",
            "state_config": {},
            "waypoints": [{
                "id": "wp1",
                "gt_entities": {},
                "is_target": True,
                "media": [abs_image_path]
            }]
        }
        
        dataset_path = export_missions_to_hf_dataset(
            missions=[mission],
            project_path=str(project_path),
            output_dir=str(output_dir),
            dataset_name="test"
        )
        
        # Check image was copied
        images_dir = Path(dataset_path) / "images"
        assert len(list(images_dir.glob("*"))) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
