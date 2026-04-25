"""
ASCII Rendering Engine
======================
Converts a NumPy BGR frame (from OpenCV) into either:
  - A 2-D list of (char, r, g, b) tuples  (colorized mode)
  - A 2-D list of chars                    (monochrome mode)

Supports:
  • Arbitrary character ramps
  • Brightness / contrast / gamma correction
  • Canny / Sobel edge blending
  • Floyd–Steinberg dithering
  • Full-color RGB mapping
  • Aspect-ratio-corrected resizing
"""

from __future__ import annotations

import logging
import math
from typing import NamedTuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class AsciiCell(NamedTuple):
    char: str
    r: int
    g: int
    b: int


class AsciiRenderer:
    """
    Stateless renderer: call render_frame() per frame.
    Build a new instance whenever the profile changes.
    """

    def __init__(self, profile) -> None:
        self.profile = profile
        self._ramp = profile.effective_ramp()
        self._ramp_len = len(self._ramp)
        # Pre-build LUT for brightness/contrast/gamma
        self._lut = self._build_lut(profile.brightness, profile.contrast, profile.gamma)

    # ─── Public API ───────────────────────────────────────────────────────────

    def render_frame(
        self, bgr_frame: np.ndarray
    ) -> list[list[AsciiCell]] | list[list[str]]:
        """
        Convert a BGR OpenCV frame to an ASCII grid.

        Returns
        -------
        list[list[AsciiCell]]  if profile.colorized is True
        list[list[str]]        otherwise
        """
        p = self.profile
        h, w = bgr_frame.shape[:2]

        # 1. Compute target dimensions
        cols, rows = self._compute_dims(w, h, p.width, p.height, p.maintain_aspect)

        # 2. Resize frame
        resized = cv2.resize(bgr_frame, (cols, rows), interpolation=cv2.INTER_AREA)

        # 3. Apply LUT (brightness/contrast/gamma)
        resized = cv2.LUT(resized, self._lut)

        # 4. Grayscale for intensity mapping
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY).astype(np.float32)

        # 5. Edge detection blend
        if p.edge_detection != "none":
            gray = self._blend_edges(gray, p)

        # 6. Dithering
        if p.dithering:
            gray = self._floyd_steinberg(gray)
        else:
            gray = np.clip(gray, 0, 255)

        # 7. Map intensity to chars
        gray_uint8 = gray.astype(np.uint8)
        char_indices = (gray_uint8.astype(np.float32) / 255.0 * (self._ramp_len - 1)).astype(np.int32)
        char_indices = np.clip(char_indices, 0, self._ramp_len - 1)

        # 8. Assemble output grid
        if p.colorized:
            return self._build_color_grid(char_indices, resized)
        else:
            return self._build_mono_grid(char_indices)

    def render_frame_to_image(
        self, bgr_frame: np.ndarray, font_size: int = 10, font_face=None
    ) -> np.ndarray:
        """
        Render ASCII grid directly onto a BGR image (for video encoding).
        Uses OpenCV putText — fast but limited font choice.
        """
        p = self.profile
        grid = self.render_frame(bgr_frame)
        if not grid or not grid[0]:
            return bgr_frame

        rows = len(grid)
        cols = len(grid[0])

        # Character cell dimensions (approximate for monospace)
        cell_w = max(6, font_size)
        cell_h = max(10, int(font_size * 1.6))

        img_w = cols * cell_w
        img_h = rows * cell_h

        # Parse background color
        bg = self._hex_to_bgr(p.output_bg_color)
        fg = self._hex_to_bgr(p.output_fg_color)

        canvas = np.full((img_h, img_w, 3), bg, dtype=np.uint8)

        font = cv2.FONT_HERSHEY_PLAIN
        scale = font_size / 14.0

        for row_idx, row in enumerate(grid):
            y = (row_idx + 1) * cell_h - 2
            for col_idx, cell in enumerate(row):
                x = col_idx * cell_w
                if p.colorized and isinstance(cell, AsciiCell):
                    color = (int(cell.b), int(cell.g), int(cell.r))
                else:
                    color = fg
                char = cell.char if isinstance(cell, AsciiCell) else cell
                if char != " ":
                    cv2.putText(canvas, char, (x, y), font, scale, color, 1, cv2.LINE_AA)

        return canvas

    # ─── Private Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _compute_dims(
        src_w: int, src_h: int, target_w: int, target_h: int, maintain_aspect: bool
    ) -> tuple[int, int]:
        """Compute (cols, rows) for ASCII grid."""
        if target_w <= 0:
            target_w = 80
        cols = target_w

        if target_h > 0:
            rows = target_h
        elif maintain_aspect:
            # Terminal chars are ~2× taller than wide, correct for aspect
            aspect = src_h / src_w
            rows = max(1, int(cols * aspect * 0.45))
        else:
            rows = max(1, int(cols * src_h / src_w))

        return cols, rows

    @staticmethod
    def _build_lut(brightness: float, contrast: float, gamma: float) -> np.ndarray:
        """Pre-compute a 256-entry LUT for brightness/contrast/gamma."""
        table = np.arange(256, dtype=np.float32)
        # Brightness
        table = table * brightness
        # Contrast: shift to center, scale, shift back
        table = (table - 128.0) * contrast + 128.0
        table = np.clip(table, 0, 255)
        # Gamma
        if abs(gamma - 1.0) > 1e-4:
            table = 255.0 * np.power(table / 255.0, 1.0 / gamma)
        table = np.clip(table, 0, 255).astype(np.uint8)
        return table

    def _blend_edges(self, gray: np.ndarray, p) -> np.ndarray:
        """Blend edge map into grayscale for enhanced character selection."""
        g_uint8 = np.clip(gray, 0, 255).astype(np.uint8)
        if p.edge_detection == "canny":
            edges = cv2.Canny(g_uint8, p.canny_low, p.canny_high).astype(np.float32)
        else:  # sobel
            ksize = p.sobel_ksize if p.sobel_ksize % 2 == 1 else p.sobel_ksize + 1
            sx = cv2.Sobel(g_uint8, cv2.CV_32F, 1, 0, ksize=ksize)
            sy = cv2.Sobel(g_uint8, cv2.CV_32F, 0, 1, ksize=ksize)
            edges = np.sqrt(sx ** 2 + sy ** 2)
            edges = np.clip(edges / edges.max() * 255, 0, 255) if edges.max() > 0 else edges

        w = float(p.edge_weight)
        blended = gray * (1.0 - w) + edges * w
        return np.clip(blended, 0, 255)

    @staticmethod
    def _floyd_steinberg(gray: np.ndarray) -> np.ndarray:
        """In-place Floyd–Steinberg dithering on a float32 grayscale image."""
        img = gray.copy()
        h, w = img.shape
        for y in range(h):
            for x in range(w):
                old = img[y, x]
                # Quantize to nearest multiple of 32 (8 levels)
                new = round(old / 32.0) * 32.0
                new = max(0.0, min(255.0, new))
                img[y, x] = new
                err = old - new
                if x + 1 < w:
                    img[y, x + 1] += err * 7 / 16
                if y + 1 < h:
                    if x > 0:
                        img[y + 1, x - 1] += err * 3 / 16
                    img[y + 1, x] += err * 5 / 16
                    if x + 1 < w:
                        img[y + 1, x + 1] += err * 1 / 16
        return np.clip(img, 0, 255)

    def _build_color_grid(
        self, char_indices: np.ndarray, bgr: np.ndarray
    ) -> list[list[AsciiCell]]:
        rows, cols = char_indices.shape
        grid: list[list[AsciiCell]] = []
        ramp = self._ramp
        for r in range(rows):
            row: list[AsciiCell] = []
            for c in range(cols):
                ch = ramp[char_indices[r, c]]
                b_val, g_val, r_val = int(bgr[r, c, 0]), int(bgr[r, c, 1]), int(bgr[r, c, 2])
                row.append(AsciiCell(ch, r_val, g_val, b_val))
            grid.append(row)
        return grid

    def _build_mono_grid(self, char_indices: np.ndarray) -> list[list[str]]:
        rows, cols = char_indices.shape
        ramp = self._ramp
        return [[ramp[char_indices[r, c]] for c in range(cols)] for r in range(rows)]

    @staticmethod
    def _hex_to_bgr(hex_color: str) -> tuple[int, int, int]:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (b, g, r)
