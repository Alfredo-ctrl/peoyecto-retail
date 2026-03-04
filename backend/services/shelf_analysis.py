"""
Shelf-specific geometric analysis for retail CV.
Shelf line detection, grid inference, bbox refinement, out-of-stock zones.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple

import sys, os
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.models.detection import Detection


@dataclass
class ShelfLine:
    """A detected horizontal shelf line."""
    y: int
    x_start: int
    x_end: int
    confidence: float


class ShelfAnalyzer:
    """
    Analyzes shelf geometry to improve detection accuracy.
    Detects shelf lines, infers product grid, refines bboxes.
    """

    def __init__(
        self,
        hough_threshold: int = 80,
        min_line_length_ratio: float = 0.25,
        max_line_gap: int = 30,
        angle_tolerance: float = 15.0,
        merge_distance: int = 20,
    ):
        self.hough_threshold = hough_threshold
        self.min_line_length_ratio = min_line_length_ratio
        self.max_line_gap = max_line_gap
        self.angle_tolerance = angle_tolerance
        self.merge_distance = merge_distance

    def detect_shelf_lines(self, img: np.ndarray) -> List[ShelfLine]:
        """Detect horizontal shelf lines using HoughLinesP + LSD."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        min_len = int(w * self.min_line_length_ratio)

        # Edge detection
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150, apertureSize=3)

        # Morphological closing to connect nearby edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 1))
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        # HoughLinesP
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, self.hough_threshold,
            minLineLength=min_len, maxLineGap=self.max_line_gap
        )

        shelf_lines = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
                if angle < self.angle_tolerance or angle > (180 - self.angle_tolerance):
                    mid_y = (y1 + y2) // 2
                    shelf_lines.append(ShelfLine(
                        y=mid_y,
                        x_start=min(x1, x2),
                        x_end=max(x1, x2),
                        confidence=1.0,
                    ))

        # Merge nearby lines
        return self._merge_lines(shelf_lines)

    def _merge_lines(self, lines: List[ShelfLine]) -> List[ShelfLine]:
        """Merge shelf lines that are within merge_distance of each other."""
        if not lines:
            return []

        sorted_lines = sorted(lines, key=lambda l: l.y)
        merged = [sorted_lines[0]]

        for line in sorted_lines[1:]:
            if abs(line.y - merged[-1].y) < self.merge_distance:
                # Merge: average y, extend x range
                prev = merged[-1]
                merged[-1] = ShelfLine(
                    y=(prev.y + line.y) // 2,
                    x_start=min(prev.x_start, line.x_start),
                    x_end=max(prev.x_end, line.x_end),
                    confidence=max(prev.confidence, line.confidence),
                )
            else:
                merged.append(line)

        return merged

    def get_shelf_rows(
        self, lines: List[ShelfLine], img_height: int
    ) -> List[Tuple[int, int]]:
        """
        Convert shelf lines to row ranges (y_top, y_bottom).
        Each row is the space between two consecutive lines.
        """
        if not lines:
            return [(0, img_height)]

        rows = []
        line_ys = [0] + [l.y for l in lines] + [img_height]

        for i in range(len(line_ys) - 1):
            y_top = line_ys[i]
            y_bottom = line_ys[i + 1]
            if y_bottom - y_top > 20:  # Min row height
                rows.append((y_top, y_bottom))

        return rows

    def refine_detections(
        self,
        detections: List[Detection],
        shelf_lines: List[ShelfLine],
        img_height: int,
        img_width: int,
    ) -> List[Detection]:
        """
        Refine detection bboxes using shelf geometry.
        - Snap bottom edge to nearest shelf line.
        - Remove detections that span multiple rows (likely false positives).
        - Adjust confidence based on shelf context.
        """
        if not shelf_lines or not detections:
            return detections

        line_ys = sorted([l.y for l in shelf_lines])
        refined = []

        for det in detections:
            x1, y1, x2, y2 = det.bbox
            bbox_height = y2 - y1
            bbox_center_y = (y1 + y2) // 2

            # Find nearest shelf line below bbox
            nearest_below = None
            min_dist = float('inf')
            for ly in line_ys:
                if ly > bbox_center_y:
                    dist = ly - y2
                    if abs(dist) < min_dist:
                        min_dist = abs(dist)
                        nearest_below = ly

            # Snap bottom if close to shelf line
            if nearest_below is not None and min_dist < bbox_height * 0.3:
                y2 = nearest_below

            # Check how many shelf rows this bbox spans
            rows_crossed = sum(1 for ly in line_ys if y1 < ly < y2)
            if rows_crossed > 1 and bbox_height > img_height * 0.4:
                # Likely a false positive spanning multiple shelves
                continue

            refined.append(Detection(
                bbox=(x1, y1, x2, y2),
                score=det.score,
                class_id=det.class_id,
                class_name=det.class_name,
            ))

        return refined

    def detect_empty_zones(
        self,
        detections: List[Detection],
        shelf_lines: List[ShelfLine],
        img_width: int,
        img_height: int,
        min_gap_ratio: float = 0.1,
    ) -> List[Tuple[int, int, int, int]]:
        """
        Detect empty zones on shelves (potential out-of-stock areas).
        Returns list of (x1, y1, x2, y2) for empty regions.
        """
        rows = self.get_shelf_rows(shelf_lines, img_height)
        empty_zones = []

        for row_top, row_bottom in rows:
            # Get detections in this row
            row_dets = [
                d for d in detections
                if d.bbox[1] < row_bottom and d.bbox[3] > row_top
            ]

            if not row_dets:
                # Entire row empty
                empty_zones.append((0, row_top, img_width, row_bottom))
                continue

            # Sort by x position
            sorted_dets = sorted(row_dets, key=lambda d: d.bbox[0])
            min_gap = int(img_width * min_gap_ratio)

            # Check left edge
            if sorted_dets[0].bbox[0] > min_gap:
                empty_zones.append((0, row_top, sorted_dets[0].bbox[0], row_bottom))

            # Check gaps between detections
            for i in range(len(sorted_dets) - 1):
                gap_start = sorted_dets[i].bbox[2]
                gap_end = sorted_dets[i + 1].bbox[0]
                if gap_end - gap_start > min_gap:
                    empty_zones.append((gap_start, row_top, gap_end, row_bottom))

            # Check right edge
            if img_width - sorted_dets[-1].bbox[2] > min_gap:
                empty_zones.append((sorted_dets[-1].bbox[2], row_top, img_width, row_bottom))

        return empty_zones
