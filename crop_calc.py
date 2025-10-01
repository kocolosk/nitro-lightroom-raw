import math

class Point:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
    
    def rotate(self, center: 'Point', theta: float) -> 'Point':
        """Rotate this point around another point by angle theta (radians)."""
        cos_th = math.cos(theta)
        sin_th = math.sin(theta)
        dx = self.x - center.x
        dy = self.y - center.y
        rx = dx * cos_th - dy * sin_th
        ry = dx * sin_th + dy * cos_th
        return Point(center.x + rx, center.y + ry)
    
class CropRect:    
    def __init__(self, json_array, rotation_degrees=0.0, orig_width=6960, orig_height=4640):
        (x1, y1), (w, h) = json_array
        self.origin = Point(x1, y1)
        self.width = orig_width if w == 0 else w
        self.height = orig_height if h == 0 else h
        self.rotation_degrees = rotation_degrees
        self.orig_width = orig_width
        self.orig_height = orig_height

    def center(self) -> Point:
        """Calculate the center point of the crop rectangle."""
        return Point(self.origin.x + 0.5 * self.width, self.origin.y + 0.5 * self.height)

    def _rotate_corners(self, theta: float) -> tuple[Point, Point]:
        """Rotate the top-left and bottom-right corners around the center by angle theta (radians)."""
        center = self.center()
        top_left = Point(self.origin.x, self.origin.y + self.height).rotate(center, theta)
        bottom_right = Point(self.origin.x + self.width, self.origin.y).rotate(center, theta)
        return top_left, bottom_right

    def _scale_factor(self, theta: float, max_width: float, max_height: float) -> float:
        """Calculate the scale factor needed to fit the rotated crop rectangle."""
        scale = 1.0
        corners = (
            Point(self.origin.x, self.origin.y), 
            Point(self.origin.x, self.origin.y + self.height), 
            Point(self.origin.x + self.width, self.origin.y), 
            Point(self.origin.x + self.width, self.origin.y + self.height)
        )
        center = self.center()
        for p in corners:
            rotated = p.rotate(center, theta)
            if rotated.x < 0:
                scale = max(scale, abs(rotated.x - center.x) / center.x)
            elif rotated.x > max_width:
                scale = max(scale, abs(rotated.x - center.x) / (max_width - center.x))
            if rotated.y < 0:
                scale = max(scale, abs(rotated.y - center.y) / center.y)
            elif rotated.y > max_height:
                scale = max(scale, abs(rotated.y - center.y) / (max_height - center.y))
        return scale
    
    def _scale_point(self, poi: Point, scale_factor: float) -> Point:
        """Scale a point away from the center by the scale factor."""
        center = self.center()
        dx = poi.x - center.x
        dy = poi.y - center.y
        return Point(center.x + dx / scale_factor, center.y + dy / scale_factor)
    
    def crop_factors(self) -> dict:
        """Calculate the crop factors (left, top, right, bottom) after rotation."""
        theta = math.radians(-1.0 * self.rotation_degrees)
        top_left_rotated, bottom_right_rotated = self._rotate_corners(theta)

        # Now scale if necessary to fit within original dimensions
        scale_factor = self._scale_factor(theta, self.orig_width, self.orig_height)
        top_left_final = self._scale_point(top_left_rotated, scale_factor)
        bottom_right_final = self._scale_point(bottom_right_rotated, scale_factor)

        # CRS crop factors are normalized to [0,1] with origin at top-left
        return {
            "crs:CropLeft": top_left_final.x / self.orig_width,
            "crs:CropTop": 1 - top_left_final.y / self.orig_height,
            "crs:CropRight": bottom_right_final.x / self.orig_width,
            "crs:CropBottom": 1 - bottom_right_final.y / self.orig_height,
            "crs:CropAngle": self.rotation_degrees,
            "crs:CropConstrainToWarp": 0,
            "crs:CropConstrainToUnitSquare": 1,
            "crs:HasCrop": True
        }
