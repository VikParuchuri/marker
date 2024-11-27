from __future__ import annotations
import copy
from typing import List

import numpy as np
from pydantic import BaseModel, field_validator, computed_field


class PolygonBox(BaseModel):
    polygon: List[List[float]]

    @field_validator('polygon')
    @classmethod
    def check_elements(cls, v: List[List[float]]) -> List[List[float]]:
        if len(v) != 4:
            raise ValueError('corner must have 4 elements')

        for corner in v:
            if len(corner) != 2:
                raise ValueError('corner must have 2 elements')

        min_x = min([corner[0] for corner in v])
        min_y = min([corner[1] for corner in v])

        # Ensure corners are clockwise from top left
        corner_error = f" .Corners are {v}"
        assert v[2][1] >= min_y, f'bottom right corner should have a greater y value than top right corner' + corner_error
        assert v[3][1] >= min_y, 'bottom left corner should have a greater y value than top left corner' + corner_error
        assert v[1][0] >= min_x, 'top right corner should have a greater x value than top left corner' + corner_error
        assert v[2][0] >= min_x, 'bottom right corner should have a greater x value than bottom left corner' + corner_error
        return v

    @property
    def height(self):
        return self.bbox[3] - self.bbox[1]

    @property
    def width(self):
        return self.bbox[2] - self.bbox[0]

    @property
    def area(self):
        return self.width * self.height

    @property
    def center(self):
        return [(self.bbox[0] + self.bbox[2]) / 2, (self.bbox[1] + self.bbox[3]) / 2]

    @property
    def size(self):
        return [self.width, self.height]

    @property
    def x_start(self):
        return self.bbox[0]

    @property
    def y_start(self):
        return self.bbox[1]

    @property
    def x_end(self):
        return self.bbox[2]

    @property
    def y_end(self):
        return self.bbox[3]

    @computed_field
    @property
    def bbox(self) -> List[float]:
        min_x = min([corner[0] for corner in self.polygon])
        min_y = min([corner[1] for corner in self.polygon])
        max_x = max([corner[0] for corner in self.polygon])
        max_y = max([corner[1] for corner in self.polygon])
        return [min_x, min_y, max_x, max_y]

    def expand(self, x_margin: float, y_margin: float) -> PolygonBox:
        new_polygon = []
        x_margin = x_margin * self.width
        y_margin = y_margin * self.height
        for idx, poly in self.polygon:
            if idx == 0:
                new_polygon.append([poly[0] - x_margin, poly[1] - y_margin])
            elif idx == 1:
                new_polygon.append([poly[0] + x_margin, poly[1] - y_margin])
            elif idx == 2:
                new_polygon.append([poly[0] + x_margin, poly[1] + y_margin])
            elif idx == 3:
                new_polygon.append([poly[0] - x_margin, poly[1] + y_margin])
        return PolygonBox(polygon=new_polygon)

    def minimum_gap(self, other: PolygonBox):
        if self.intersection_pct(other) > 0:
            return 0

        def dist(p1, p2):
            return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5

        left = other.bbox[2] < self.bbox[0]
        right = self.bbox[2] < other.bbox[0]
        bottom = other.bbox[3] < self.bbox[1]
        top = self.bbox[3] < other.bbox[1]
        if top and left:
            return dist((self.bbox[0], self.bbox[3]), (other.bbox[2], other.bbox[1]))
        elif left and bottom:
            return dist((self.bbox[0], self.bbox[1]), (other.bbox[2], other.bbox[3]))
        elif bottom and right:
            return dist((self.bbox[2], self.bbox[1]), (other.bbox[0], other.bbox[3]))
        elif right and top:
            return dist((self.bbox[2], self.bbox[3]), (other.bbox[0], other.bbox[1]))
        elif left:
            return self.bbox[0] - other.bbox[2]
        elif right:
            return other.bbox[0] - self.bbox[2]
        elif bottom:
            return self.bbox[1] - other.bbox[3]
        elif top:
            return other.bbox[1] - self.bbox[3]
        else:
            return 0

    def center_distance(self, other: PolygonBox, x_weight: float = 1, y_weight: float = 1, absolute=False):
        if not absolute:
            return ((self.center[0] - other.center[0]) ** 2 * x_weight + (self.center[1] - other.center[1]) ** 2 * y_weight) ** 0.5
        else:
            return abs(self.center[0] - other.center[0]) * x_weight + abs(self.center[1] - other.center[1]) * y_weight

    def rescale(self, old_size, new_size):
        # Point is in x, y format
        page_width, page_height = old_size
        img_width, img_height = new_size

        width_scaler = img_width / page_width
        height_scaler = img_height / page_height

        new_corners = copy.deepcopy(self.polygon)
        for corner in new_corners:
            corner[0] = corner[0] * width_scaler
            corner[1] = corner[1] * height_scaler
        return PolygonBox(polygon=new_corners)

    def fit_to_bounds(self, bounds):
        new_corners = copy.deepcopy(self.polygon)
        for corner in new_corners:
            corner[0] = max(min(corner[0], bounds[2]), bounds[0])
            corner[1] = max(min(corner[1], bounds[3]), bounds[1])
        self.polygon = new_corners

    def overlap_x(self, other: PolygonBox):
        return max(0, min(self.bbox[2], other.bbox[2]) - max(self.bbox[0], other.bbox[0]))

    def overlap_y(self, other: PolygonBox):
        return max(0, min(self.bbox[3], other.bbox[3]) - max(self.bbox[1], other.bbox[1]))

    def intersection_area(self, other: PolygonBox):
        return self.overlap_x(other) * self.overlap_y(other)

    def intersection_pct(self, other: PolygonBox):
        if self.area == 0:
            return 0

        intersection = self.intersection_area(other)
        return intersection / self.area

    def merge(self, others: List[PolygonBox]) -> PolygonBox:
        corners = []
        for i in range(len(self.polygon)):
            x_coords = [self.polygon[i][0]] + [other.polygon[i][0] for other in others]
            y_coords = [self.polygon[i][1]] + [other.polygon[i][1] for other in others]
            min_x = min(x_coords)
            min_y = min(y_coords)
            max_x = max(x_coords)
            max_y = max(y_coords)

            if i == 0:
                corners.append([min_x, min_y])
            elif i == 1:
                corners.append([max_x, min_y])
            elif i == 2:
                corners.append([max_x, max_y])
            elif i == 3:
                corners.append([min_x, max_y])
        return PolygonBox(polygon=corners)

    @classmethod
    def from_bbox(cls, bbox: List[float], ensure_nonzero_area=False):
        if ensure_nonzero_area:
            bbox = list(bbox)
            bbox[2] = max(bbox[2], bbox[0] + 1)
            bbox[3] = max(bbox[3], bbox[1] + 1)
        return cls(polygon=[[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]]])
