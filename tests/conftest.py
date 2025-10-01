"""
Pytest configuration and shared fixtures for crop_calc tests.
"""
import pytest
from crop_calc import CropRect, Point


@pytest.fixture
def tolerance():
    """Standard floating point tolerance for test comparisons."""
    return 1e-6


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
        'cropRect': [[25, 25], [50, 50]],  # JSON array for CropRect
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
        'cropRect': [[0, 0], [50, 50]],
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

@pytest.fixture
def crop_test_case(request):
    """Generic fixture to provide a crop test case by name."""
    test_cases = {
        "basic": {
            'cropRect': [[25, 25], [50, 50]],  # JSON array for CropRect
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
        },
        "9O0A0700": {
            'rotation': -0.895569,
            'expected': { 'crs:CropLeft': 0.006364, 'crs:CropTop': 0.022911 },
        },
        "9O0A0824": {
            'rotation': 2.103972,
            'expected': { 'crs:CropLeft': 0.037721, 'crs:CropTop': 0.0 },
        },
        "9O0A1667" : {
            'cropRect': [[527.9708682405662,131.51999177562675],[6248,4165.333333333332]],
            'rotation': -2.22,
            'expected': { 'crs:CropTop': 0.100371, 'crs:CropLeft': 0.064603, 'crs:CropBottom': 0.945238, 'crs:CropRight': 0.984813 }
        },
        "9O0A1670": {
            'cropRect': [[842.6005306871207,583.562899233074],[5876.999999999999,3918]],
            'rotation': -2.744139,
            'expected': { 'crs:CropTop': 0.060639, 'crs:CropLeft': 0.108072, 'crs:CropBottom': 0.843428, 'crs:CropRight': 0.978451, 'crs:CropAngle': -2.744139 }
        }
    }
    return test_cases.get(request.param, None)

