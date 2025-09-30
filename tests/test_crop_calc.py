import unittest
import math
from crop_calc import CropCalculator

class TestCropCalculator(unittest.TestCase):
    
    def setUp(self):
        self.calc = CropCalculator()
        
        # Fixture data with cropRect, rotation_degrees, and expected CRS output
        self.test_fixtures = [
            {
                "name": "no_rotation_origin",
                "cropRect": [[0, 0], [10, 10]],
                "width": 10,
                "height": 10,
                "rotation_degrees": 0,
                "expected_crs": { "left": 0.0, "top": 0.0, "right": 1.0, "bottom": 1.0 }
            },
            {
                "name": "no_rotation_offset",
                "cropRect": [[5, 5], [10, 10]],
                "width": 20,
                "height": 20,
                "rotation_degrees": 0,
                "expected_crs": { "left": 0.25, "top": 0.25, "right": 0.75, "bottom": 0.75 }
            },
            {
                "name": "45_degree_rotation",
                "cropRect": [[0, 0], [10, 10]],
                "width": 10,
                "height": 10,
                "rotation_degrees": 45,
                "expected_crs": { "left": 0.5, "top": 0.5 *(1 - math.sqrt(2)), "right": 0.5, "bottom": 0.5 * (1 + math.sqrt(2)) }
            },
            # {
            #     "name": "9O0A1667",
            #     "cropRect": [[527.9708682405662,131.51999177562675],[6248,4165.333333333332]],
            #     "width": 6960,
            #     "height": 4640,
            #     "rotation_degrees": -2.22,
            #     "expected_crs": { "top": 0.122243, "left": 0.089471, "bottom": 0.944856, "right": 0.985442 }
            # },
            {
                "name": "9O0A1670",
                "width": 6960,
                "height": 4640,
                "cropRect": [[842.6005306871207,583.562899233074],[5876.999999999999,3918]],
                "rotation_degrees": -2.744139,
                "expected_crs": { "top": 0.060646, "left": 0.108317, "bottom": 0.843514, "right": 0.978784 }
            }
        ]
    
    def test_center_coordinate(self):
        # Test basic center calculation
        center = self.calc.center_coordinate((0, 0), (10, 20))
        self.assertEqual(center, (5.0, 10.0))
        
        # Test with offset origin
        center = self.calc.center_coordinate((5, 5), (10, 10))
        self.assertEqual(center, (10.0, 10.0))
    
    def test_rotate_point_no_rotation(self):
        # Test rotation by 0 degrees (no change)
        rotated = self.calc.rotate_point((5, 5), (0, 0), 0)
        self.assertAlmostEqual(rotated[0], 5.0, places=7)
        self.assertAlmostEqual(rotated[1], 5.0, places=7)
    
    def test_rotate_point_90_degrees(self):
        # Test rotation by 90 degrees around origin
        rotated = self.calc.rotate_point((1, 0), (0, 0), math.pi/2)
        self.assertAlmostEqual(rotated[0], 0.0, places=7)
        self.assertAlmostEqual(rotated[1], 1.0, places=7)
    
    def test_rotate_point_180_degrees(self):
        # Test rotation by 180 degrees
        rotated = self.calc.rotate_point((1, 1), (0, 0), math.pi)
        self.assertAlmostEqual(rotated[0], -1.0, places=7)
        self.assertAlmostEqual(rotated[1], -1.0, places=7)
    
    def test_crs_coords_from_fixtures(self):
        """Test CRS coordinate calculation using fixture data"""
        for fixture in self.test_fixtures:
            with self.subTest(fixture=fixture["name"]):
                # Extract cropRect in the format expected by crs_coords: ((x1, y1), (width, height))
                crop_rect = (tuple(fixture["cropRect"][0]), tuple(fixture["cropRect"][1]))
                rotation_degrees = fixture["rotation_degrees"]
                expected_crs = fixture["expected_crs"]
                width = fixture.get("width", 1)
                height = fixture.get("height", 1)
                
                # Calculate CRS coordinates
                actual_crs = self.calc.crs_coords(crop_rect, rotation_degrees, orig_width=width, orig_height=height)

                # Assert each coordinate matches expected values
                self.assertAlmostEqual(actual_crs["left"], expected_crs["left"], places=7,
                                     msg=f"Left coordinate mismatch in {fixture['name']}")
                self.assertAlmostEqual(actual_crs["top"], expected_crs["top"], places=7,
                                     msg=f"Top coordinate mismatch in {fixture['name']}")
                self.assertAlmostEqual(actual_crs["right"], expected_crs["right"], places=7,
                                     msg=f"Right coordinate mismatch in {fixture['name']}")
                self.assertAlmostEqual(actual_crs["bottom"], expected_crs["bottom"], places=7,
                                     msg=f"Bottom coordinate mismatch in {fixture['name']}")
    
    def test_add_custom_fixture(self):
        """Example of how to add and test a custom fixture"""
        custom_fixture = {
            "name": "custom_45_degree",
            "cropRect": [[2, 2], [4, 4]],
            "rotation_degrees": 45,
            "expected_crs": {
                "left": 2 - 2*math.sqrt(2),
                "top": 2 + 2*math.sqrt(2),
                "right": 6 - 2*math.sqrt(2),
                "bottom": 6 + 2*math.sqrt(2)
            }
        }
        
        crop_rect = (tuple(custom_fixture["cropRect"][0]), tuple(custom_fixture["cropRect"][1]))
        rotation_degrees = custom_fixture["rotation_degrees"]
        expected_crs = custom_fixture["expected_crs"]
        
        actual_crs = self.calc.crs_coords(crop_rect, rotation_degrees)
        
        self.assertAlmostEqual(actual_crs["left"], expected_crs["left"], places=7)
        self.assertAlmostEqual(actual_crs["top"], expected_crs["top"], places=7)
        self.assertAlmostEqual(actual_crs["right"], expected_crs["right"], places=7)
        self.assertAlmostEqual(actual_crs["bottom"], expected_crs["bottom"], places=7)


if __name__ == '__main__':
    unittest.main()