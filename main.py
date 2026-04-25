#!/usr/bin/env python3
"""
ASCII Video Converter — Entry Point
====================================
Initializes logging, applies the Qt stylesheet, and launches the main window.

Usage:
    python main.py [--debug] [--file /path/to/video.mp4]

Architecture overview:
  main.py
    └─ ui/main_window.py       ← Top-level Qt window, orchestrates everything
         ├─ ui/settings_panel  ← All render controls, emits RenderProfile
         ├─ ui/preview_panel   ← Side-by-side comparison with scrubber
         ├─ ui/plugins_panel   ← Plugin pipeline manager
         ├─ ui/batch_panel     ← Multi-file queue processor
         └─ ui/debug_panel     ← Live metrics and log output
  core/
    ├─ ascii_renderer.py       ← Pure frame→ASCII conversion (stateless)
    └─ pipeline.py             ← Streaming encode pipeline (threaded)
  plugins/
    └─ base_plugin.py          ← Plugin base class + built-in filters
  presets/
    └─ profiles.py             ← RenderProfile dataclass + built-in presets
  config/
    └─ manager.py              ← JSON config persistence (~/.ascii_video_converter/)
"""

import argparse
import logging
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))


def configure_logging(debug: bool = False) -> None:
    """Set up root logger with a clean format."""
    level = logging.DEBUG if debug else logging.INFO
    fmt = "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s"
    datefmt = "%H:%M:%S"
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt)
    # Quieten noisy third-party loggers
    for noisy in ["PIL", "cv2", "matplotlib"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)


def check_dependencies() -> list[str]:
    """Return list of missing required packages."""
    missing = []
    checks = [
        ("cv2", "opencv-python"),
        ("numpy", "numpy"),
        ("PIL", "Pillow"),
        ("PyQt6", "PyQt6"),
    ]
    for mod, pkg in checks:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ASCII Video Converter — convert videos to ASCII art"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--file", metavar="PATH", help="Open a video file on startup")
    parser.add_argument("--preset", metavar="KEY", help="Apply a preset on startup")
    args = parser.parse_args()

    configure_logging(args.debug)
    log = logging.getLogger(__name__)

    # Dependency check
    missing = check_dependencies()
    if missing:
        print(f"ERROR: Missing required packages: {', '.join(missing)}")
        print(f"Install with:  pip install {' '.join(missing)}")
        return 1

    log.info("Starting ASCII Video Converter")

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont

    app = QApplication(sys.argv)
    app.setApplicationName("ASCII Video Converter")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("ASCIIConverter")

    # Apply dark stylesheet
    from ui.styles import STYLESHEET
    app.setStyleSheet(STYLESHEET)

    # Set default monospace font
    font = QFont("JetBrains Mono", 11)
    font.setStyleHint(QFont.StyleHint.Monospace)
    app.setFont(font)

    from ui.main_window import MainWindow
    window = MainWindow()

    # Handle CLI arguments
    if args.file:
        if os.path.exists(args.file):
            window._load_video(args.file)
        else:
            log.warning("File not found: %s", args.file)

    if args.preset:
        window._apply_preset(args.preset)

    window.show()
    log.info("Window displayed — entering event loop")

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
