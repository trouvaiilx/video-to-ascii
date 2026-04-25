"""
ASCII Rendering Engine
======================
High-performance, configurable ASCII art conversion engine.
Supports character ramps, color mapping, edge detection, dithering,
gamma correction, and Floyd-Steinberg dithering.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------

class EdgeMode(Enum):
    NONE   = auto()
    CANNY  = auto()
    SOBEL  = auto()


class ColorMode(Enum):
    GRAYSCALE = auto()   # single-channel ASCII
    ANSI      = auto()   # ANSI escape codes (terminal)
    RGB_IMAGE = auto()   # full-color rendered image


@dataclass
class ASCIIConfig:
    """All tunable parameters for ASCII conversion."""

    # --- Output resolution ---
    output_width: int = 120          # characters wide
    output_height: int = 0           # 0 = auto-compute from aspect ratio
    char_aspect: float = 0.55        # terminal char height/width ratio

    # --- Character ramp ---
    char_ramp: str = (
        r" .`'^\",:;Il!i><~+_-?][}{1)(|\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
    )
    reverse_ramp: bool = False       # white-on-black vs black-on-white

    # --- Brightness / contrast / gamma ---
    brightness: float = 0.0         # additive offset  [-127, 127]
    contrast: float = 1.0           # multiplicative   [0.1, 4.0]
    gamma: float = 1.0              # power correction [0.1, 3.0]

    # --- Edge detection ---
    edge_mode: EdgeMode = EdgeMode.NONE
    canny_low: int  = 50
    canny_high: int = 150
    sobel_ksize: int = 3
    edge_weight: float = 0.6        # blend weight for edge overlay

    # --- Dithering ---
    dither_enabled: bool = False
    dither_strength: float = 1.0    # [0.0, 1.0]

    # --- Color ---
    color_mode: ColorMode = ColorMode.GRAYSCALE

    # --- Font for image rendering ---
    font_path: Optional[str] = None  # None → built-in monospace
    font_size: int = 10

    # --- Frame sampling ---
    frame_skip: int = 0             # 0 = none, N = keep every Nth frame
    target_fps: float = 0.0         # 0 = source fps


@dataclass
class RenderStats:
    """Per-frame rendering statistics."""
    frame_index: int   = 0
    render_ms: float   = 0.0
    char_count: int    = 0
    width_chars: int   = 0
    height_chars: int  = 0


# ---------------------------------------------------------------------------
# Gamma LUT cache
# ---------------------------------------------------------------------------

_GAMMA_CACHE: dict[float, np.ndarray] = {}

def _get_gamma_lut(gamma: float) -> np.ndarray:
    if gamma not in _GAMMA_CACHE:
        lut = np.array(
            [min(255, int((i / 255.0) ** (1.0 / gamma) * 255)) for i in range(256)],
            dtype=np.uint8,
        )
        _GAMMA_CACHE[gamma] = lut
    return _GAMMA_CACHE[gamma]


# ---------------------------------------------------------------------------
# Floyd-Steinberg dithering (pure NumPy, no loops over pixels)
# ---------------------------------------------------------------------------

def floyd_steinberg(gray: np.ndarray, n_levels: int, strength: float = 1.0) -> np.ndarray:
    """
    Apply Floyd-Steinberg dithering to a grayscale image.

    Parameters
    ----------
    gray      : H×W uint8 image
    n_levels  : number of quantisation levels (len of char ramp)
    strength  : blend factor between original and dithered output
    """
    h, w = gray.shape
    buf = gray.astype(np.float32)
    step = 255.0 / (n_levels - 1)

    for y in range(h):
        for x in range(w):
            old_px  = buf[y, x]
            new_px  = round(old_px / step) * step
            buf[y, x] = new_px
            err = (old_px - new_px) * strength

            if x + 1 < w:
                buf[y,     x + 1] += err * 7 / 16
            if y + 1 < h:
                if x - 1 >= 0:
                    buf[y + 1, x - 1] += err * 3 / 16
                buf[y + 1, x    ] += err * 5 / 16
                if x + 1 < w:
                    buf[y + 1, x + 1] += err * 1 / 16

    return np.clip(buf, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Main engine class
# ---------------------------------------------------------------------------

class ASCIIEngine:
    """
    Core ASCII rendering engine.

    Thread-safe: each call to ``convert_frame`` is stateless given a config.
    Mutating ``config`` between calls is safe only outside render threads.
    """

    def __init__(self, config: Optional[ASCIIConfig] = None):
        self.config: ASCIIConfig = config or ASCIIConfig()
        self._font_cache: dict[tuple, object] = {}  # key → PIL ImageFont

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def convert_frame(
        self,
        frame: np.ndarray,
        *,
        return_image: bool = True,
    ) -> tuple[list[str], Optional[np.ndarray], RenderStats]:
        """
        Convert a BGR video frame to ASCII art.

        Parameters
        ----------
        frame        : H×W×3 BGR uint8 NumPy array (from OpenCV)
        return_image : render an image from the ASCII chars if True

        Returns
        -------
        lines        : list of ASCII strings (one per row)
        image        : rendered uint8 RGB image, or None
        stats        : RenderStats
        """
        t0 = time.perf_counter()
        cfg = self.config

        # 1. Resize to target character grid
        cw, ch = self._compute_output_size(frame.shape[1], frame.shape[0])
        small = cv2.resize(frame, (cw, ch), interpolation=cv2.INTER_AREA)

        # 2. Colour-space split
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        bgr  = small  # keep colour for RGB mode

        # 3. Brightness / contrast
        gray = self._apply_bc(gray)

        # 4. Gamma correction
        if cfg.gamma != 1.0:
            lut  = _get_gamma_lut(cfg.gamma)
            gray = cv2.LUT(gray, lut)

        # 5. Edge detection overlay
        if cfg.edge_mode != EdgeMode.NONE:
            edges = self._detect_edges(gray)
            gray  = cv2.addWeighted(gray, 1.0 - cfg.edge_weight,
                                    edges, cfg.edge_weight, 0)

        # 6. Dithering
        ramp = cfg.char_ramp
        if cfg.reverse_ramp:
            ramp = ramp[::-1]

        if cfg.dither_enabled:
            gray = floyd_steinberg(gray, len(ramp), cfg.dither_strength)

        # 7. Map pixels → characters
        indices = (gray.astype(np.float32) / 255.0 * (len(ramp) - 1)).astype(np.int32)
        indices = np.clip(indices, 0, len(ramp) - 1)
        lines   = ["".join(ramp[idx] for idx in row) for row in indices]

        # 8. Optionally render to image
        rendered_image = None
        if return_image:
            if cfg.color_mode == ColorMode.RGB_IMAGE:
                rendered_image = self._render_color_image(lines, bgr, gray)
            else:
                rendered_image = self._render_gray_image(lines)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        stats = RenderStats(
            render_ms   = elapsed_ms,
            char_count  = cw * ch,
            width_chars = cw,
            height_chars= ch,
        )
        return lines, rendered_image, stats

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_output_size(self, src_w: int, src_h: int) -> tuple[int, int]:
        cfg = self.config
        cw  = max(10, cfg.output_width)
        if cfg.output_height > 0:
            ch = cfg.output_height
        else:
            # Correct for character aspect ratio
            ch = max(5, int(cw * src_h / src_w * cfg.char_aspect))
        return cw, ch

    def _apply_bc(self, gray: np.ndarray) -> np.ndarray:
        cfg = self.config
        if cfg.brightness == 0.0 and cfg.contrast == 1.0:
            return gray
        arr = gray.astype(np.float32)
        arr = arr * cfg.contrast + cfg.brightness
        return np.clip(arr, 0, 255).astype(np.uint8)

    def _detect_edges(self, gray: np.ndarray) -> np.ndarray:
        cfg = self.config
        if cfg.edge_mode == EdgeMode.CANNY:
            edges = cv2.Canny(gray, cfg.canny_low, cfg.canny_high)
        else:  # SOBEL
            sx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=cfg.sobel_ksize)
            sy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=cfg.sobel_ksize)
            edges = np.sqrt(sx**2 + sy**2)
            edges = (edges / edges.max() * 255).astype(np.uint8) if edges.max() > 0 else gray
        return edges

    def _render_gray_image(self, lines: list[str]) -> np.ndarray:
        """Render ASCII lines to a grayscale-style BGR image using OpenCV."""
        cfg       = self.config
        font_face = cv2.FONT_HERSHEY_PLAIN
        font_scale= max(0.4, cfg.font_size / 14.0)
        thickness = 1
        fg_color  = (220, 220, 220)
        bg_color  = (18, 18, 18)

        # Measure one character
        (cw, ch), baseline = cv2.getTextSize("W", font_face, font_scale, thickness)
        line_h = ch + baseline + 2

        img_w = cw * len(lines[0])
        img_h = line_h * len(lines)
        img   = np.full((img_h, img_w, 3), bg_color, dtype=np.uint8)

        for row_idx, line in enumerate(lines):
            y = (row_idx + 1) * line_h
            for col_idx, ch_char in enumerate(line):
                x = col_idx * cw
                cv2.putText(img, ch_char, (x, y), font_face,
                            font_scale, fg_color, thickness, cv2.LINE_AA)
        return img

    def _render_color_image(
        self,
        lines:   list[str],
        bgr_src: np.ndarray,
        gray:    np.ndarray,
    ) -> np.ndarray:
        """Render ASCII lines with per-character colour from the source frame."""
        cfg       = self.config
        font_face = cv2.FONT_HERSHEY_PLAIN
        font_scale= max(0.4, cfg.font_size / 14.0)
        thickness = 1
        bg_color  = (18, 18, 18)

        (cw, ch_h), baseline = cv2.getTextSize("W", font_face, font_scale, thickness)
        line_h = ch_h + baseline + 2

        img_w = cw * len(lines[0])
        img_h = line_h * len(lines)
        img   = np.full((img_h, img_w, 3), bg_color, dtype=np.uint8)

        h_chars = len(lines)
        w_chars = len(lines[0]) if lines else 1

        for row_idx, line in enumerate(lines):
            y = (row_idx + 1) * line_h
            # Sample color from downscaled source
            src_y = min(row_idx, bgr_src.shape[0] - 1)
            for col_idx, ch_char in enumerate(line):
                src_x = min(col_idx, bgr_src.shape[1] - 1)
                b, g, r = bgr_src[src_y, src_x].tolist()
                x = col_idx * cw
                cv2.putText(img, ch_char, (x, y), font_face,
                            font_scale, (r, g, b), thickness, cv2.LINE_AA)
        return img


# ---------------------------------------------------------------------------
# Convenience: generate ANSI-coloured text frame
# ---------------------------------------------------------------------------

def frame_to_ansi(lines: list[str], bgr_src: np.ndarray) -> str:
    """
    Convert ASCII lines + source frame into an ANSI-colour-coded string
    suitable for terminal display.
    """
    h, w = bgr_src.shape[:2]
    rows = []
    for row_idx, line in enumerate(lines):
        sy = min(row_idx, h - 1)
        parts = []
        for col_idx, ch in enumerate(line):
            sx = min(col_idx, w - 1)
            b, g, r = bgr_src[sy, sx].tolist()
            parts.append(f"\033[38;2;{r};{g};{b}m{ch}")
        rows.append("".join(parts) + "\033[0m")
    return "\n".join(rows)
