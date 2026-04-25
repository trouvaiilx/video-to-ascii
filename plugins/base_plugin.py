"""
Plugin base class and built-in filter plugins.
Plugins receive a BGR NumPy frame and return a modified BGR frame.
"""

from __future__ import annotations
import abc
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginParam:
    name: str
    label: str
    type: str          # "float" | "int" | "bool" | "choice"
    default: Any
    min_val: Any = None
    max_val: Any = None
    choices: list = field(default_factory=list)


class BasePlugin(abc.ABC):
    """All filter plugins must subclass this."""

    #: Unique identifier (used as dict key)
    plugin_id: str = "base"
    #: Human-readable name shown in UI
    display_name: str = "Base Plugin"
    #: Short description for tooltip
    description: str = ""
    #: Parameter definitions for UI generation
    params: list[PluginParam] = []

    def __init__(self) -> None:
        self._param_values: dict[str, Any] = {p.name: p.default for p in self.params}

    def set_param(self, name: str, value: Any) -> None:
        self._param_values[name] = value

    def get_param(self, name: str) -> Any:
        return self._param_values.get(name)

    @abc.abstractmethod
    def process(self, frame: np.ndarray) -> np.ndarray:
        """Apply the filter. Input and output are BGR uint8 frames."""
        ...


# ─── Built-in Plugins ─────────────────────────────────────────────────────────

class GaussianBlurPlugin(BasePlugin):
    plugin_id = "gaussian_blur"
    display_name = "Gaussian Blur"
    description = "Smooth the frame before ASCII conversion to reduce noise."
    params = [
        PluginParam("kernel_size", "Kernel Size", "int", 3, 1, 31),
        PluginParam("sigma", "Sigma", "float", 0.0, 0.0, 10.0),
    ]

    def process(self, frame: np.ndarray) -> np.ndarray:
        k = int(self._param_values["kernel_size"])
        if k % 2 == 0:
            k += 1
        sigma = float(self._param_values["sigma"])
        return cv2.GaussianBlur(frame, (k, k), sigma)


class SharpenPlugin(BasePlugin):
    plugin_id = "sharpen"
    display_name = "Unsharp Mask (Sharpen)"
    description = "Enhance fine details before ASCII rendering."
    params = [
        PluginParam("strength", "Strength", "float", 1.0, 0.0, 5.0),
    ]

    def process(self, frame: np.ndarray) -> np.ndarray:
        strength = float(self._param_values["strength"])
        blurred = cv2.GaussianBlur(frame, (0, 0), 3)
        return cv2.addWeighted(frame, 1.0 + strength, blurred, -strength, 0)


class EmbossPlugin(BasePlugin):
    plugin_id = "emboss"
    display_name = "Emboss"
    description = "Apply emboss effect for a 3-D texture look."
    params = []

    _kernel = np.array([[-2, -1, 0], [-1, 1, 1], [0, 1, 2]], dtype=np.float32)

    def process(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        embossed = cv2.filter2D(gray, -1, self._kernel) + 128
        embossed = np.clip(embossed, 0, 255).astype(np.uint8)
        return cv2.cvtColor(embossed, cv2.COLOR_GRAY2BGR)


class ColorBoostPlugin(BasePlugin):
    plugin_id = "color_boost"
    display_name = "Color / Saturation Boost"
    description = "Increase color saturation for vivid colorized ASCII."
    params = [
        PluginParam("saturation", "Saturation", "float", 1.5, 0.0, 4.0),
    ]

    def process(self, frame: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
        sat = float(self._param_values["saturation"])
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * sat, 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


class DepthEnhancePlugin(BasePlugin):
    plugin_id = "depth_enhance"
    display_name = "Depth / Contrast Enhance"
    description = "CLAHE-based local contrast enhancement for depth perception."
    params = [
        PluginParam("clip_limit", "Clip Limit", "float", 2.0, 0.5, 10.0),
        PluginParam("tile_size", "Tile Size", "int", 8, 4, 32),
    ]

    def process(self, frame: np.ndarray) -> np.ndarray:
        clip = float(self._param_values["clip_limit"])
        tile = int(self._param_values["tile_size"])
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(tile, tile))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


class PixelatePlugin(BasePlugin):
    plugin_id = "pixelate"
    display_name = "Pixelate"
    description = "Pre-pixelate frame for a chunky retro ASCII look."
    params = [
        PluginParam("block_size", "Block Size", "int", 4, 1, 32),
    ]

    def process(self, frame: np.ndarray) -> np.ndarray:
        bs = max(1, int(self._param_values["block_size"]))
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (w // bs, h // bs), interpolation=cv2.INTER_LINEAR)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


# ─── Plugin Registry ──────────────────────────────────────────────────────────

BUILTIN_PLUGINS: list[type[BasePlugin]] = [
    GaussianBlurPlugin,
    SharpenPlugin,
    EmbossPlugin,
    ColorBoostPlugin,
    DepthEnhancePlugin,
    PixelatePlugin,
]

PLUGIN_REGISTRY: dict[str, type[BasePlugin]] = {
    cls.plugin_id: cls for cls in BUILTIN_PLUGINS
}


def get_plugin(plugin_id: str) -> BasePlugin | None:
    cls = PLUGIN_REGISTRY.get(plugin_id)
    return cls() if cls else None
