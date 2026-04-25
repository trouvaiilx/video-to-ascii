"""
Filter Plugin System
====================
Defines the FilterPlugin base class and ships several built-in filters.
New filters can be added by subclassing FilterPlugin and registering
them via PLUGIN_REGISTRY.

Each plugin receives a BGR uint8 NumPy array and must return a BGR uint8 array.
Plugins are applied in order before ASCII conversion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

import cv2
import numpy as np

from core.pipeline import FilterPlugin


# ---------------------------------------------------------------------------
# Plugin registry
# ---------------------------------------------------------------------------

PLUGIN_REGISTRY: dict[str, Type[FilterPlugin]] = {}

def register_plugin(cls: Type[FilterPlugin]) -> Type[FilterPlugin]:
    PLUGIN_REGISTRY[cls.name] = cls
    return cls


# ---------------------------------------------------------------------------
# Built-in filter plugins
# ---------------------------------------------------------------------------

@register_plugin
class GaussianBlurPlugin(FilterPlugin):
    name        = "gaussian_blur"
    description = "Smooth the frame to reduce noise before ASCII conversion"
    enabled     = False

    def __init__(self):
        self.kernel_size: int   = 5    # must be odd
        self.sigma:       float = 1.0

    def process(self, frame: np.ndarray) -> np.ndarray:
        ks = self.kernel_size | 1  # ensure odd
        return cv2.GaussianBlur(frame, (ks, ks), self.sigma)

    def get_params(self) -> dict:
        return {"kernel_size": self.kernel_size, "sigma": self.sigma}

    def set_params(self, params: dict):
        self.kernel_size = int(params.get("kernel_size", 5))
        self.sigma       = float(params.get("sigma", 1.0))


@register_plugin
class SharpenPlugin(FilterPlugin):
    name        = "sharpen"
    description = "Enhance edge detail before ASCII conversion"
    enabled     = False

    def __init__(self):
        self.strength: float = 1.0

    def process(self, frame: np.ndarray) -> np.ndarray:
        kernel = np.array([
            [ 0, -1,  0],
            [-1,  4 + self.strength, -1],
            [ 0, -1,  0],
        ], dtype=np.float32)
        sharpened = cv2.filter2D(frame, -1, kernel)
        return np.clip(sharpened, 0, 255).astype(np.uint8)

    def get_params(self) -> dict:
        return {"strength": self.strength}

    def set_params(self, params: dict):
        self.strength = float(params.get("strength", 1.0))


@register_plugin
class EmbossPlugin(FilterPlugin):
    name        = "emboss"
    description = "Emboss / relief effect — great for cinematic ASCII"
    enabled     = False

    def process(self, frame: np.ndarray) -> np.ndarray:
        kernel = np.array([
            [-2, -1, 0],
            [-1,  1, 1],
            [ 0,  1, 2],
        ], dtype=np.float32)
        embossed = cv2.filter2D(frame, -1, kernel) + 128
        return np.clip(embossed, 0, 255).astype(np.uint8)


@register_plugin
class ContrastEnhancePlugin(FilterPlugin):
    name        = "contrast_enhance"
    description = "CLAHE adaptive histogram equalisation per channel"
    enabled     = False

    def __init__(self):
        self.clip_limit:   float = 2.0
        self.tile_grid:    int   = 8

    def process(self, frame: np.ndarray) -> np.ndarray:
        clahe = cv2.createCLAHE(
            clipLimit=self.clip_limit,
            tileGridSize=(self.tile_grid, self.tile_grid),
        )
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def get_params(self) -> dict:
        return {"clip_limit": self.clip_limit, "tile_grid": self.tile_grid}

    def set_params(self, params: dict):
        self.clip_limit = float(params.get("clip_limit", 2.0))
        self.tile_grid  = int(params.get("tile_grid", 8))


@register_plugin
class DepthEdgePlugin(FilterPlugin):
    name        = "depth_edge"
    description = "Accentuate depth cues via bilateral + Laplacian overlay"
    enabled     = False

    def __init__(self):
        self.blend: float = 0.4

    def process(self, frame: np.ndarray) -> np.ndarray:
        bilateral = cv2.bilateralFilter(frame, 9, 75, 75)
        gray   = cv2.cvtColor(bilateral, cv2.COLOR_BGR2GRAY)
        lap    = cv2.Laplacian(gray, cv2.CV_64F)
        lap    = np.clip(np.abs(lap), 0, 255).astype(np.uint8)
        lap3   = cv2.cvtColor(lap, cv2.COLOR_GRAY2BGR)
        result = cv2.addWeighted(bilateral, 1.0, lap3, self.blend, 0)
        return np.clip(result, 0, 255).astype(np.uint8)

    def get_params(self) -> dict:
        return {"blend": self.blend}

    def set_params(self, params: dict):
        self.blend = float(params.get("blend", 0.4))


@register_plugin
class ChromaticAberrationPlugin(FilterPlugin):
    name        = "chromatic_aberration"
    description = "RGB channel shift for a glitchy, digital aesthetic"
    enabled     = False

    def __init__(self):
        self.shift_px: int = 2

    def process(self, frame: np.ndarray) -> np.ndarray:
        s = self.shift_px
        b, g, r = cv2.split(frame)
        # Shift red left, blue right
        rows, cols = frame.shape[:2]
        M_r = np.float32([[1, 0, -s], [0, 1, 0]])
        M_b = np.float32([[1, 0,  s], [0, 1, 0]])
        r_shifted = cv2.warpAffine(r, M_r, (cols, rows))
        b_shifted = cv2.warpAffine(b, M_b, (cols, rows))
        return cv2.merge([b_shifted, g, r_shifted])

    def get_params(self) -> dict:
        return {"shift_px": self.shift_px}

    def set_params(self, params: dict):
        self.shift_px = int(params.get("shift_px", 2))


@register_plugin
class VignettePlugin(FilterPlugin):
    name        = "vignette"
    description = "Dark edges to focus attention on the centre"
    enabled     = False

    def __init__(self):
        self.strength: float = 0.5
        self._mask: Optional[np.ndarray] = None
        self._mask_shape: tuple = (0, 0)

    def _build_mask(self, h: int, w: int) -> np.ndarray:
        if (h, w) != self._mask_shape:
            Y = np.linspace(-1, 1, h)
            X = np.linspace(-1, 1, w)
            Xg, Yg = np.meshgrid(X, Y)
            mask = 1 - np.sqrt(Xg**2 + Yg**2) / np.sqrt(2)
            mask = np.clip(mask, 0, 1).astype(np.float32)
            self._mask       = mask
            self._mask_shape = (h, w)
        return self._mask

    def process(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        mask = self._build_mask(h, w)
        alpha = 1.0 - self.strength * (1 - mask)
        result = (frame.astype(np.float32) * alpha[:, :, np.newaxis])
        return np.clip(result, 0, 255).astype(np.uint8)

    def get_params(self) -> dict:
        return {"strength": self.strength}

    def set_params(self, params: dict):
        self.strength = float(params.get("strength", 0.5))
        self._mask_shape = (0, 0)  # invalidate cache


# ---------------------------------------------------------------------------
# Plugin factory / manager
# ---------------------------------------------------------------------------

class PluginManager:
    """Manages an ordered list of active filter plugins."""

    def __init__(self):
        self._plugins: list[FilterPlugin] = []

    def add(self, name: str, **kwargs) -> FilterPlugin:
        cls = PLUGIN_REGISTRY.get(name)
        if cls is None:
            raise KeyError(f"No plugin named '{name}'. Available: {list(PLUGIN_REGISTRY)}")
        plugin = cls()
        if kwargs:
            plugin.set_params(kwargs)
        self._plugins.append(plugin)
        return plugin

    def remove(self, name: str):
        self._plugins = [p for p in self._plugins if p.name != name]

    def get(self, name: str) -> Optional[FilterPlugin]:
        for p in self._plugins:
            if p.name == name:
                return p
        return None

    def move_up(self, name: str):
        idx = next((i for i, p in enumerate(self._plugins) if p.name == name), None)
        if idx and idx > 0:
            self._plugins[idx - 1], self._plugins[idx] = \
                self._plugins[idx], self._plugins[idx - 1]

    def move_down(self, name: str):
        idx = next((i for i, p in enumerate(self._plugins) if p.name == name), None)
        if idx is not None and idx < len(self._plugins) - 1:
            self._plugins[idx], self._plugins[idx + 1] = \
                self._plugins[idx + 1], self._plugins[idx]

    @property
    def plugins(self) -> list[FilterPlugin]:
        return list(self._plugins)

    def to_dict(self) -> list[dict]:
        return [
            {"name": p.name, "enabled": p.enabled, "params": p.get_params()}
            for p in self._plugins
        ]

    def from_dict(self, data: list[dict]):
        self._plugins.clear()
        for item in data:
            p = self.add(item["name"])
            p.enabled = item.get("enabled", True)
            p.set_params(item.get("params", {}))
