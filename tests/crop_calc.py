import math

class CropCalculator:

    def center_coordinate(self, pos, size):
        """Convert from lower-left corner + size to center coordinate."""
        x1, y1 = pos
        w, h = size
        cx = x1 + 0.5 * w
        cy = y1 + 0.5 * h
        return (cx, cy)
    
    def rotate_point(self, point, center, theta):
        """Rotate point (px, py) around center (cx, cy) by angle theta (radians)."""
        px, py = point
        cx, cy = center
        cth = math.cos(theta)
        sth = math.sin(theta)
        dx = px - cx
        dy = py - cy
        rx = dx * cth - dy * sth
        ry = dx * sth + dy * cth
        return (cx + rx, cy + ry)
    
    def top_left(self, pos, size, rotation_degrees):
        x1, y1 = pos
        w, h = size
        y2 = y1 + h
        center = self.center_coordinate((x1, y1), (w, h))
        return self.rotate_point((x1, y2), center, math.radians(rotation_degrees))
    
    def bottom_right(self, pos, size, rotation_degrees):
        x1, y1 = pos
        w, h = size
        x2 = x1 + w
        center = self.center_coordinate((x1, y1), (w, h))
        return self.rotate_point((x2, y1), center, math.radians(rotation_degrees))

    def crs_coords(self, cropRect, rotation_degrees):
        (x1, y1), (w, h) = cropRect
        top_left_rotated = self.top_left((x1, y1), (w, h), rotation_degrees)
        bot_right_rotated = self.bottom_right((x1, y1), (w, h), rotation_degrees)
        crs = {
            "left": top_left_rotated[0],
            "top": top_left_rotated[1],
            "right": bot_right_rotated[0],
            "bottom": bot_right_rotated[1],
        }
        return crs
    
