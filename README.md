# ASCII Video Converter

A high-performance, cross-platform desktop application that converts videos into customizable ASCII art videos.

## Features

### 🎨 Rendering Engine
- **8 built-in presets**: Terminal Classic, Cinematic ASCII, Colored HD, Low/Medium/High Quality, Edge Art, Dithered Retro
- **Custom character ramps**: Define your own dark→light character progression
- **Resolution control**: Width/height with automatic aspect-ratio correction
- **Image adjustments**: Brightness, Contrast, Gamma (real-time LUT)
- **Edge detection**: Canny or Sobel with adjustable thresholds and blend weight
- **Floyd–Steinberg dithering**: Classic error-diffusion for retro aesthetics
- **Colorized ASCII**: Full RGB mapping rendered as image frames

### ⚡ Processing Pipeline
- **Streaming architecture**: Never loads full video into memory — frame-by-frame
- **Multi-threaded workers**: Auto-scales to CPU core count
- **GPU acceleration**: NVENC via FFmpeg when NVIDIA hardware is present
- **Progress tracking**: ETA, current FPS, CPU/RAM usage
- **Cancellation**: Stop encoding at any time

### 🎛 Filter Plugins
Built-in plugins, chainable in any order:
- Gaussian Blur
- Unsharp Mask (Sharpen)
- Emboss
- Color / Saturation Boost
- Depth / Contrast Enhance (CLAHE)
- Pixelate

### 📁 Output Formats
- **MP4**: H.264 encoded video with embedded ASCII frames
- **GIF**: Animated GIF with adjustable frame rate
- **Image Sequence**: Individual PNG frames in a directory
- **Text Stream**: ASCII text file with frame-delimited output

### 🖥 Interface
- Dark-mode Qt6 UI with monospace terminal aesthetic
- Side-by-side original vs ASCII comparison panel
- Video scrubber with playback preview
- Drag-and-drop video input
- Batch processing queue
- Debug panel with live metrics and bottleneck analysis
- Save/load custom presets

## Installation

```bash
pip install -r requirements.txt
# Also requires FFmpeg in PATH:
# macOS:   brew install ffmpeg
# Ubuntu:  sudo apt install ffmpeg
# Windows: https://ffmpeg.org/download.html
```

## Usage

```bash
# Launch GUI
python main.py

# Open with a file
python main.py --file /path/to/video.mp4

# Apply a preset on startup
python main.py --preset cinematic_ascii

# Enable debug logging
python main.py --debug
```

## Architecture

```
ascii_video_converter/
├── main.py                    # Entry point, CLI args, Qt app init
├── core/
│   ├── ascii_renderer.py      # Stateless frame→ASCII converter
│   └── pipeline.py            # Streaming encode/preview pipeline
├── plugins/
│   └── base_plugin.py         # Plugin base + 6 built-in filters
├── presets/
│   └── profiles.py            # RenderProfile dataclass + 8 presets
├── config/
│   └── manager.py             # JSON config (~/.ascii_video_converter/)
└── ui/
    ├── styles.py              # Full Qt dark-mode stylesheet
    ├── widgets.py             # Reusable widgets (DropZone, StatCard…)
    ├── main_window.py         # Top-level window + toolbar + menu
    ├── settings_panel.py      # All render controls (scrollable)
    ├── preview_panel.py       # Side-by-side comparison + scrubber
    ├── plugins_panel.py       # Plugin pipeline manager
    ├── batch_panel.py         # Multi-file batch queue
    └── debug_panel.py         # Live metrics + log output
```

## Adding Custom Plugins

```python
from plugins.base_plugin import BasePlugin, PluginParam, PLUGIN_REGISTRY
import numpy as np

class MyFilter(BasePlugin):
    plugin_id = "my_filter"
    display_name = "My Custom Filter"
    description = "Does something cool."
    params = [
        PluginParam("strength", "Strength", "float", 1.0, 0.0, 5.0),
    ]

    def process(self, frame: np.ndarray) -> np.ndarray:
        # frame is BGR uint8 — return same shape
        return frame  # your transform here

# Register it
PLUGIN_REGISTRY["my_filter"] = MyFilter
```

## Requirements

- Python 3.10+
- PyQt6 ≥ 6.5
- OpenCV (opencv-python) ≥ 4.8
- NumPy ≥ 1.24
- Pillow ≥ 10.0
- psutil ≥ 5.9
- FFmpeg (system binary, in PATH)

Optional:
- NVIDIA GPU + NVENC-capable FFmpeg for hardware-accelerated encoding
