import pytest
import math
from crop_calc import CropRect, Point


class TestPoint:
    """Test the Point class functionality."""
    
    def test_point_initialization(self):
        """Test Point initialization."""
        point = Point(10.5, 20.3)
        assert point.x == 10.5
        assert point.y == 20.3
    
    def test_point_rotation_no_rotation(self):
        """Test point rotation with 0 degrees."""
        point = Point(5, 0)
        center = Point(0, 0)
        rotated = point.rotate(center, 0)
        assert abs(rotated.x - 5) < 1e-10
        assert abs(rotated.y - 0) < 1e-10
    
    def test_point_rotation_90_degrees(self):
        """Test point rotation with 90 degrees."""
        point = Point(1, 0)
        center = Point(0, 0)
        rotated = point.rotate(center, math.pi/2)  # 90 degrees in radians
        assert abs(rotated.x - 0) < 1e-10
        assert abs(rotated.y - 1) < 1e-10


class TestCropRect:
    """Test the CropRect class functionality."""
    
    @pytest.fixture
    def basic_crop_rect(self):
        """Basic crop rectangle for testing - small crop within larger image."""
        return CropRect([[50, 50], [100, 80]])
    
    @pytest.fixture
    def centered_crop_rect(self):
        """Centered crop rectangle for testing - small crop in center."""
        return CropRect([[25, 25], [50, 50]])
    
    @pytest.fixture
    def origin_crop_rect(self):
        """Crop rectangle starting at origin."""
        return CropRect([[0, 0], [50, 50]])
    
    def test_crop_rect_initialization(self):
        """Test CropRect initialization from JSON array."""
        crop_rect = CropRect([[10, 20], [100, 80]])
        assert crop_rect.origin.x == 10
        assert crop_rect.origin.y == 20
        assert crop_rect.width == 100
        assert crop_rect.height == 80
    
    def test_center_calculation(self, basic_crop_rect):
        """Test center point calculation."""
        center = basic_crop_rect.center()
        assert center.x == 100  # 50 + 0.5 * 100
        assert center.y == 90   # 50 + 0.5 * 80
    
    def test_crop_factors_structure(self, basic_crop_rect):
        """Test that crop_factors returns all required keys."""
        basic_crop_rect.original_width = 200
        basic_crop_rect.original_height = 160
        factors = basic_crop_rect.crop_factors()
        
        # Verify all required keys are present
        expected_keys = [
            "crs:CropLeft", "crs:CropTop", "crs:CropRight", "crs:CropBottom",
            "crs:CropAngle", "crs:CropConstrainToWarp", "crs:CropConstrainToUnitSquare",
            "crs:HasCrop"
        ]
        for key in expected_keys:
            assert key in factors
        
        # Test data types
        assert isinstance(factors["crs:CropLeft"], (int, float))
        assert isinstance(factors["crs:CropTop"], (int, float))
        assert isinstance(factors["crs:CropRight"], (int, float))
        assert isinstance(factors["crs:CropBottom"], (int, float))
        assert isinstance(factors["crs:CropAngle"], (int, float))
        assert isinstance(factors["crs:CropConstrainToWarp"], int)
        assert isinstance(factors["crs:CropConstrainToUnitSquare"], int)
        assert isinstance(factors["crs:HasCrop"], bool)
    
    def test_crop_factors_no_rotation(self, basic_crop_rect):
        """Test crop factors with no rotation."""
        basic_crop_rect.original_width = 200
        basic_crop_rect.original_height = 160
        factors = basic_crop_rect.crop_factors()
        
        # With no rotation, crop should match original rectangle
        assert factors["crs:CropAngle"] == 0.0
        assert factors["crs:CropConstrainToWarp"] == 0
        assert factors["crs:CropConstrainToUnitSquare"] == 1
        assert factors["crs:HasCrop"] is True
        
        # Crop factors should be normalized to [0, 1]
        assert 0 <= factors["crs:CropLeft"] <= 1
        assert 0 <= factors["crs:CropTop"] <= 1
        assert 0 <= factors["crs:CropRight"] <= 1
        assert 0 <= factors["crs:CropBottom"] <= 1
        
        # Left should be less than right, top should be less than bottom
        assert factors["crs:CropLeft"] < factors["crs:CropRight"]
        assert factors["crs:CropTop"] < factors["crs:CropBottom"]
    
    def test_crop_factors_with_rotation(self, basic_crop_rect):
        """Test crop factors with 45-degree rotation."""
        basic_crop_rect.rotation_degrees = 45.0
        basic_crop_rect.original_width = 200
        basic_crop_rect.original_height = 160
        factors = basic_crop_rect.crop_factors()
        
        assert factors["crs:CropAngle"] == 45.0
        assert 0 <= factors["crs:CropLeft"] <= 1
        assert 0 <= factors["crs:CropTop"] <= 1
        assert 0 <= factors["crs:CropRight"] <= 1
        assert 0 <= factors["crs:CropBottom"] <= 1
        
        # Left should be less than right, top should be less than bottom
        assert factors["crs:CropLeft"] < factors["crs:CropRight"]
        assert factors["crs:CropTop"] < factors["crs:CropBottom"]
    
    def test_crop_factors_negative_rotation(self, basic_crop_rect):
        """Test crop factors with negative rotation."""
        basic_crop_rect.rotation_degrees = -30.0
        basic_crop_rect.original_width = 200
        basic_crop_rect.original_height = 160
        factors = basic_crop_rect.crop_factors()
        
        assert factors["crs:CropAngle"] == -30.0
        assert 0 <= factors["crs:CropLeft"] <= 1
        assert 0 <= factors["crs:CropRight"] <= 1
        assert 0 <= factors["crs:CropTop"] <= 1
        assert 0 <= factors["crs:CropBottom"] <= 1
    
    def test_crop_factors_90_degree_rotation(self, centered_crop_rect):
        """Test crop factors with 90-degree rotation."""
        centered_crop_rect.rotation_degrees = 90.0
        centered_crop_rect.original_width = 100
        centered_crop_rect.original_height = 100
        factors = centered_crop_rect.crop_factors()

        assert factors["crs:CropAngle"] == 90.0
        # Verify the crop factors are within valid range
        assert 0 <= factors["crs:CropLeft"] <= 1
        assert 0 <= factors["crs:CropRight"] <= 1
        assert 0 <= factors["crs:CropTop"] <= 1
        assert 0 <= factors["crs:CropBottom"] <= 1
    
    def test_rotate_corners_no_rotation(self, basic_crop_rect):
        """Test _rotate_corners method with no rotation."""
        top_left, bottom_right = basic_crop_rect._rotate_corners(0.0)
        
        # With no rotation, should match expected corners
        # Note: top_left is actually bottom_left in image coordinates
        assert abs(top_left.x - basic_crop_rect.origin.x) < 1e-10
        assert abs(top_left.y - (basic_crop_rect.origin.y + basic_crop_rect.height)) < 1e-10
        assert abs(bottom_right.x - (basic_crop_rect.origin.x + basic_crop_rect.width)) < 1e-10
        assert abs(bottom_right.y - basic_crop_rect.origin.y) < 1e-10
    
    def test_scale_point_method(self, basic_crop_rect):
        """Test the _scale_point method."""
        center = basic_crop_rect.center()
        test_point = Point(125, 110)
        scaled_point = basic_crop_rect._scale_point(test_point, 2.0)
        
        # Point should be scaled towards center
        expected_x = center.x + (test_point.x - center.x) / 2.0
        expected_y = center.y + (test_point.y - center.y) / 2.0
        assert abs(scaled_point.x - expected_x) < 1e-10
        assert abs(scaled_point.y - expected_y) < 1e-10
    
    def test_scale_factor_no_rotation_fits(self, basic_crop_rect):
        """Test scale factor calculation when crop fits without scaling."""
        scale_factor = basic_crop_rect._scale_factor(0.0, 200, 160)
        assert scale_factor == 1.0  # No scaling needed if it fits
    
    @pytest.mark.parametrize("rotation", [0, 15, 30, 45, 60, 90, 180, 270])
    def test_crop_factors_various_rotations(self, basic_crop_rect, rotation):
        """Test crop factors with various rotation angles."""
        basic_crop_rect.rotation_degrees = rotation
        basic_crop_rect.original_width = 200
        basic_crop_rect.original_height = 160
        factors = basic_crop_rect.crop_factors()

        # All crop factors should be valid
        assert 0 <= factors["crs:CropLeft"] <= 1
        assert 0 <= factors["crs:CropRight"] <= 1
        assert 0 <= factors["crs:CropTop"] <= 1
        assert 0 <= factors["crs:CropBottom"] <= 1
        
        # After rotation, we can't guarantee left < right or top < bottom due to coordinate transformation
        # but the crop area should be non-zero
        width = abs(factors["crs:CropRight"] - factors["crs:CropLeft"])
        height = abs(factors["crs:CropBottom"] - factors["crs:CropTop"])
        assert width > 0
        assert height > 0
        assert factors["crs:CropAngle"] == rotation
    
    @pytest.mark.parametrize("json_array,expected_width,expected_height", [
        ([[0, 0], [100, 100]], 100, 100),
        ([[50, 25], [200, 150]], 200, 150),
        ([[10.5, 20.3], [75.7, 90.2]], 75.7, 90.2),
    ])
    def test_crop_rect_with_various_inputs(self, json_array, expected_width, expected_height):
        """Test CropRect with various JSON array inputs."""
        crop_rect = CropRect(json_array)
        assert crop_rect.width == expected_width
        assert crop_rect.height == expected_height
        assert crop_rect.origin.x == json_array[0][0]
        assert crop_rect.origin.y == json_array[0][1]
    
    def test_crop_factors_consistency(self, basic_crop_rect):
        """Test that crop factors are consistent between multiple calls."""
        basic_crop_rect.rotation_degrees = 45.0
        basic_crop_rect.original_width = 200
        basic_crop_rect.original_height = 160
        factors1 = basic_crop_rect.crop_factors()
        factors2 = basic_crop_rect.crop_factors()

        for key in factors1:
            if isinstance(factors1[key], float):
                assert abs(factors1[key] - factors2[key]) < 1e-10
            else:
                assert factors1[key] == factors2[key]

    
    @pytest.mark.parametrize("crop_test_case", [
        "known_crop_test_case_1", "known_crop_test_case_rotated"
    ], indirect=True)
    def test_with_fixture_example(self, crop_test_case):
        """Example of using a fixture for specific test cases."""
        test_case = crop_test_case
        crop_rect = CropRect(test_case['cropRect'], test_case['rotation'], test_case['orig_width'], test_case['orig_height'])
        factors = crop_rect.crop_factors()
        
        tolerance = 1e-10
        expected = test_case['expected']
        
        for key, expected_value in expected.items():
            if isinstance(expected_value, float):
                assert abs(factors[key] - expected_value) < tolerance, f"Failed for {key}: got {factors[key]}, expected {expected_value}"
            else:
                assert factors[key] == expected_value, f"Failed for {key}: got {factors[key]}, expected {expected_value}"