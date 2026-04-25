"""
Preset profiles for ASCII Video Converter.
Each preset defines a full rendering configuration.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json


@dataclass
class RenderProfile:
    """Complete rendering configuration."""
    name: str
    description: str

    # ASCII character ramp (dark → light)
    char_ramp: str = " .:-=+*#%@"
    custom_ramp: str = ""
    use_custom_ramp: bool = False

    # Resolution
    width: int = 120
    height: int = 0  # 0 = auto from aspect ratio
    scale_factor: float = 1.0
    maintain_aspect: bool = True

    # Brightness / Contrast / Gamma
    brightness: float = 1.0   # multiplier
    contrast: float = 1.0     # multiplier
    gamma: float = 1.0        # gamma correction exponent

    # Edge detection
    edge_detection: str = "none"   # none | canny | sobel
    canny_low: int = 50
    canny_high: int = 150
    sobel_ksize: int = 3
    edge_weight: float = 0.5

    # Dithering
    dithering: bool = False
    dither_method: str = "floyd_steinberg"

    # Color
    colorized: bool = False
    color_mode: str = "ansi"  # ansi | rgb_image | terminal_256

    # Font
    font_family: str = "Courier New"
    font_size: int = 10

    # Temporal
    frame_skip: int = 0
    target_fps: float = 0.0   # 0 = source fps

    # Output
    output_format: str = "mp4"   # mp4 | gif | image_seq | txt_stream
    output_quality: int = 23     # CRF for mp4
    output_bg_color: str = "#000000"
    output_fg_color: str = "#00FF00"

    # GPU
    use_gpu: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RenderProfile":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def effective_ramp(self) -> str:
        if self.use_custom_ramp and self.custom_ramp:
            return self.custom_ramp
        return self.char_ramp


# ─── Built-in Presets ──────────────────────────────────────────────────────────

PRESETS: dict[str, RenderProfile] = {
    "terminal_classic": RenderProfile(
        name="Terminal Classic",
        description="Low-res green-on-black terminal style",
        char_ramp=" .:-=+*#%@",
        width=80,
        colorized=False,
        output_bg_color="#000000",
        output_fg_color="#00FF00",
        font_family="Courier New",
        font_size=12,
        output_format="mp4",
    ),
    "cinematic_ascii": RenderProfile(
        name="Cinematic ASCII",
        description="High-resolution black & white cinematic look",
        char_ramp=" `·.,;:!|/\\tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
        width=180,
        contrast=1.2,
        gamma=0.9,
        edge_detection="canny",
        canny_low=30,
        canny_high=100,
        edge_weight=0.4,
        output_bg_color="#0a0a0a",
        output_fg_color="#e8e8e8",
        font_size=8,
        output_format="mp4",
    ),
    "colored_hd": RenderProfile(
        name="Colored HD",
        description="Full-color high-definition ASCII rendering",
        char_ramp=" .:-=+*#%@",
        width=160,
        colorized=True,
        color_mode="rgb_image",
        brightness=1.1,
        contrast=1.1,
        font_size=9,
        output_format="mp4",
    ),
    "low_quality": RenderProfile(
        name="Low Quality (Fast)",
        description="Fast preview-quality rendering",
        char_ramp=" .:#@",
        width=60,
        scale_factor=0.5,
        frame_skip=2,
        output_format="gif",
        output_quality=28,
    ),
    "medium_quality": RenderProfile(
        name="Medium Quality",
        description="Balanced quality and performance",
        char_ramp=" .:-=+*#%@",
        width=120,
        contrast=1.05,
        output_format="mp4",
        output_quality=23,
    ),
    "high_quality": RenderProfile(
        name="High Quality",
        description="Maximum quality output",
        char_ramp=" `·.,;:!|/\\tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
        width=200,
        contrast=1.1,
        gamma=0.95,
        edge_detection="canny",
        dithering=True,
        output_format="mp4",
        output_quality=18,
    ),
    "edge_art": RenderProfile(
        name="Edge Art",
        description="Emphasis on edge detection for sketch-like output",
        char_ramp=" .:;=+#@",
        width=140,
        edge_detection="sobel",
        sobel_ksize=5,
        edge_weight=0.8,
        contrast=1.3,
        output_bg_color="#000000",
        output_fg_color="#ffffff",
        output_format="mp4",
    ),
    "dithered_retro": RenderProfile(
        name="Dithered Retro",
        description="Floyd-Steinberg dithered retro aesthetic",
        char_ramp=" .:#@",
        width=100,
        dithering=True,
        dither_method="floyd_steinberg",
        contrast=1.15,
        output_bg_color="#1a1a2e",
        output_fg_color="#e94560",
        output_format="gif",
    ),
}
