"""
Advanced Image Preprocessing for Retail Shelf Detection.
CLAHE, denoising, perspective rectification, section splitting.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class ImageSection:
    """A section of the original image with coordinate offset info."""
    image: np.ndarray
    offset_x: int
    offset_y: int
    original_w: int
    original_h: int


class AdvancedPreprocessor:
    """
    Multi-stage image preprocessing for maximum detection recall.
    Pipeline: denoise -> CLAHE -> perspective fix -> section split.
    """

    def __init__(
        self,
        clahe_clip: float = 3.0,
        clahe_grid: Tuple[int, int] = (8, 8),
        denoise_h: int = 7,
        n_sections: int = 3,
        section_overlap: float = 0.15,
        enable_clahe: bool = True,
        enable_denoise: bool = False,
        enable_perspective: bool = True,
    ):
        self.clahe_clip = clahe_clip
        self.clahe_grid = clahe_grid
        self.denoise_h = denoise_h
        self.n_sections = n_sections
        self.section_overlap = section_overlap
        self.enable_clahe = enable_clahe
        self.enable_denoise = enable_denoise
        self.enable_perspective = enable_perspective

    def full_pipeline(self, image: np.ndarray) -> np.ndarray:
        """Run full preprocessing pipeline on image."""
        result = image.copy()

        if self.enable_denoise:
            result = self.denoise(result)

        if self.enable_clahe:
            result = self.apply_clahe(result)

        if self.enable_perspective:
            result = self.auto_rectify_perspective(result)

        return result

    def apply_clahe(self, img: np.ndarray) -> np.ndarray:
        """CLAHE on L channel of LAB color space."""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(
            clipLimit=self.clahe_clip, tileGridSize=self.clahe_grid
        )
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def apply_clahe_sections(self, img: np.ndarray, grid: int = 3) -> np.ndarray:
        """Apply CLAHE independently to NxN grid sections for local contrast."""
        h, w = img.shape[:2]
        result = img.copy()
        sh, sw = h // grid, w // grid

        for i in range(grid):
            for j in range(grid):
                y1, y2 = i * sh, (i + 1) * sh if i < grid - 1 else h
                x1, x2 = j * sw, (j + 1) * sw if j < grid - 1 else w
                section = result[y1:y2, x1:x2]
                result[y1:y2, x1:x2] = self.apply_clahe(section)

        return result

    def denoise(self, img: np.ndarray) -> np.ndarray:
        """Non-Local Means Denoising."""
        return cv2.fastNlMeansDenoisingColored(
            img, None, self.denoise_h, self.denoise_h, 7, 21
        )

    def auto_rectify_perspective(self, img: np.ndarray) -> np.ndarray:
        """
        Detect dominant horizontal lines (shelves) and correct perspective skew.
        Falls back to original if no strong lines detected.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=80,
            minLineLength=img.shape[1] // 4, maxLineGap=30
        )

        if lines is None or len(lines) < 2:
            return img

        # Find dominant angle from horizontal lines
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
            if abs(angle) < 20:
                angles.append(angle)

        if not angles:
            return img

        median_angle = np.median(angles)
        if abs(median_angle) < 0.5:
            return img

        # Rotate to correct skew
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        corrected = cv2.warpAffine(
            img, M, (w, h), flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE
        )
        return corrected

    def split_sections(
        self, img: np.ndarray, n_cols: Optional[int] = None,
        n_rows: Optional[int] = None, overlap: Optional[float] = None
    ) -> List[ImageSection]:
        """
        Split image into overlapping sections for focused detection.
        Returns sections with offset metadata for coordinate remapping.
        """
        n_cols = n_cols or self.n_sections
        overlap = overlap or self.section_overlap
        h, w = img.shape[:2]
        sections = []

        col_step = w // n_cols
        overlap_px = int(col_step * overlap)

        rows = n_rows or 1
        row_step = h // rows
        row_overlap_px = int(row_step * overlap) if rows > 1 else 0

        for r in range(rows):
            y1 = max(0, r * row_step - row_overlap_px)
            y2 = min(h, (r + 1) * row_step + row_overlap_px) if r < rows - 1 else h

            for c in range(n_cols):
                x1 = max(0, c * col_step - overlap_px)
                x2 = min(w, (c + 1) * col_step + overlap_px) if c < n_cols - 1 else w

                sections.append(ImageSection(
                    image=img[y1:y2, x1:x2].copy(),
                    offset_x=x1,
                    offset_y=y1,
                    original_w=w,
                    original_h=h,
                ))

        return sections

    def generate_enhanced_variants(self, img: np.ndarray) -> List[np.ndarray]:
        """Generate multiple enhanced versions for multi-inference."""
        variants = [img]

        # CLAHE enhanced
        variants.append(self.apply_clahe(img))

        # Brightness boost
        bright = cv2.convertScaleAbs(img, alpha=1.3, beta=20)
        variants.append(bright)

        # Sharpened
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        sharp = cv2.filter2D(img, -1, kernel)
        variants.append(sharp)

        return variants

    def auto_white_balance(self, img: np.ndarray) -> np.ndarray:
        """Simple gray-world white balance correction."""
        result = img.copy().astype(np.float32)
        avg_b, avg_g, avg_r = cv2.mean(result)[:3]
        avg_gray = (avg_b + avg_g + avg_r) / 3
        result[:, :, 0] *= avg_gray / (avg_b + 1e-6)
        result[:, :, 1] *= avg_gray / (avg_g + 1e-6)
        result[:, :, 2] *= avg_gray / (avg_r + 1e-6)
        return np.clip(result, 0, 255).astype(np.uint8)
