"""
Pytest configuration and shared fixtures for crop_calc tests.
"""
import pytest
from crop_calc import CropRect, Point


@pytest.fixture
def tolerance():
    """Standard floating point tolerance for test comparisons."""
    return 1e-10


@pytest.fixture
def sample_crop_rects():
    """Collection of sample crop rectangles for testing."""
    return {
        'basic': CropRect([[50, 50], [100, 80]]),
        'centered': CropRect([[25, 25], [50, 50]]),
        'origin': CropRect([[0, 0], [50, 50]]),
        'large': CropRect([[100, 150], [400, 300]]),
        'small': CropRect([[10, 15], [20, 25]]),
        'float_coords': CropRect([[10.5, 20.3], [75.7, 90.2]])
    }


@pytest.fixture
def standard_image_dimensions():
    """Standard image dimensions for testing."""
    return {
        'hd': (1920, 1080),
        'fullhd': (1920, 1080),
        '4k': (3840, 2160),
        'square': (1000, 1000),
        'portrait': (800, 1200),
        'landscape': (1200, 800)
    }


# You can add your specific test case fixtures here
# Example:
@pytest.fixture
def known_crop_test_case_1():
    """Test case with known expected CRS values."""
    return {
        'input': [[25, 25], [50, 50]],  # JSON array for CropRect
        'rotation': 0.0,
        'orig_width': 100,
        'orig_height': 100,
        'expected': {
            'crs:CropLeft': 0.25,
            'crs:CropTop': 0.25,
            'crs:CropRight': 0.75,
            'crs:CropBottom': 0.75,
            'crs:CropAngle': 0.0,
            'crs:HasCrop': True
        }
    }

@pytest.fixture 
def known_crop_test_case_rotated():
    """Test case with rotation and known expected values."""
    return {
        'input': [[0, 0], [50, 50]],
        'rotation': 45.0,
        'orig_width': 100,
        'orig_height': 100,
        'expected': {
            # You would calculate and fill in the expected values here
            'crs:CropAngle': 45.0,
            'crs:HasCrop': True
            # Add other expected values as you determine them
        }
    }