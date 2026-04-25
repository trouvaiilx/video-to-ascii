"""
FFmpeg Encoder / Decoder
========================
Thin wrapper around FFmpeg subprocess for encoding processed ASCII frames
into MP4, GIF, or image sequences, with optional NVENC GPU acceleration.

The encoder receives rendered BGR images (from the ASCII engine) and writes
them to the output container via an FFmpeg pipe.  This avoids any intermediate
temp files and keeps memory usage flat even for large videos.

GPU Acceleration
----------------
When NVENC is available and ``use_gpu=True``, the encoder uses
``h264_nvenc`` with ``-preset p4`` for a good speed/quality balance.
Falls back to libx264 silently if NVENC is absent.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Iterator, Optional

import cv2
import numpy as np


class OutputFormat(Enum):
    MP4        = "mp4"
    GIF        = "gif"
    IMAGE_SEQ  = "images"
    TEXT_DUMP  = "txt"


@dataclass
class EncoderConfig:
    output_path:   str         = "output.mp4"
    format:        OutputFormat = OutputFormat.MP4
    fps:           float        = 25.0
    crf:           int          = 23          # libx264 quality (lower = better)
    nvenc_preset:  str          = "p4"        # NVENC preset
    use_gpu:       bool         = False       # attempt NVENC
    gif_scale:     int          = 480         # max width for GIF output
    image_ext:     str          = "png"
    ffmpeg_extra:  list[str]    = field(default_factory=list)


# ---------------------------------------------------------------------------
# FFmpeg availability check
# ---------------------------------------------------------------------------

def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def nvenc_available() -> bool:
    """Quick probe: try encoding a 1-frame dummy with h264_nvenc."""
    if not ffmpeg_available():
        return False
    try:
        result = subprocess.run(
            ["ffmpeg", "-f", "lavfi", "-i", "nullsrc=s=16x16:r=1",
             "-t", "0.04", "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Video encoder (streaming via pipe)
# ---------------------------------------------------------------------------

class VideoEncoder:
    """
    Accepts BGR frames and writes them to a video file via FFmpeg.

    Usage::

        enc = VideoEncoder(config, width=1280, height=720)
        enc.open()
        for frame in frames:
            enc.write_frame(frame)
        enc.close()
    """

    def __init__(self, config: EncoderConfig, width: int, height: int):
        self.config = config
        self.width  = width
        self.height = height
        self._proc: Optional[subprocess.Popen] = None
        self._frame_count = 0

    def open(self):
        if not ffmpeg_available():
            raise RuntimeError(
                "ffmpeg not found on PATH. Install FFmpeg to enable video export."
            )

        cfg = self.config
        fps = max(1.0, cfg.fps)

        # --- Choose video codec ---
        if cfg.use_gpu and nvenc_available():
            vcodec = ["h264_nvenc", "-preset", cfg.nvenc_preset, "-rc", "vbr", "-cq", str(cfg.crf)]
        elif cfg.format == OutputFormat.MP4:
            vcodec = ["libx264", "-crf", str(cfg.crf), "-preset", "fast"]
        else:
            vcodec = []

        # --- Build FFmpeg command ---
        cmd = [
            "ffmpeg",
            "-y",                                    # overwrite output
            "-f", "rawvideo",                        # input format
            "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{self.width}x{self.height}",
            "-r", str(fps),
            "-i", "-",                               # stdin
        ]

        if cfg.format == OutputFormat.MP4:
            cmd += ["-c:v"] + (vcodec or ["libx264", "-crf", str(cfg.crf)])
            cmd += ["-pix_fmt", "yuv420p"]
            cmd += cfg.ffmpeg_extra
            cmd += [cfg.output_path]

        elif cfg.format == OutputFormat.GIF:
            # Two-pass palettegen for high-quality GIF
            palette_path = str(Path(cfg.output_path).with_suffix(".palette.png"))
            # Pass 1: generate palette
            pass1 = [
                "ffmpeg", "-y",
                "-f", "rawvideo", "-vcodec", "rawvideo",
                "-pix_fmt", "bgr24",
                "-s", f"{self.width}x{self.height}",
                "-r", str(fps),
                "-i", cfg.output_path + ".tmp.avi",  # will be written first
                f"-vf", f"fps={fps},scale={cfg.gif_scale}:-1:flags=lanczos,palettegen",
                palette_path,
            ]
            # We handle GIF as a post-process step; for now write raw AVI
            cmd = [
                "ffmpeg", "-y",
                "-f", "rawvideo", "-vcodec", "rawvideo",
                "-pix_fmt", "bgr24",
                "-s", f"{self.width}x{self.height}",
                "-r", str(fps),
                "-i", "-",
                "-c:v", "rawvideo",
                cfg.output_path + ".tmp.avi",
            ]
            self._gif_path = cfg.output_path
            self._tmp_avi  = cfg.output_path + ".tmp.avi"
            self._palette  = palette_path
            self._fps      = fps
            self._scale    = cfg.gif_scale

        elif cfg.format == OutputFormat.IMAGE_SEQ:
            out_dir = Path(cfg.output_path)
            out_dir.mkdir(parents=True, exist_ok=True)
            self._image_dir = out_dir
            self._image_ext = cfg.image_ext
            self._proc = None   # no subprocess for image sequences
            return

        else:
            # TEXT_DUMP — no video encoding
            self._proc = None
            return

        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def write_frame(self, bgr_frame: np.ndarray):
        cfg = self.config

        if cfg.format == OutputFormat.IMAGE_SEQ:
            fname = self._image_dir / f"frame_{self._frame_count:06d}.{self._image_ext}"
            cv2.imwrite(str(fname), bgr_frame)
            self._frame_count += 1
            return

        if cfg.format == OutputFormat.TEXT_DUMP:
            self._frame_count += 1
            return

        if self._proc and self._proc.stdin:
            # Ensure correct dimensions
            if bgr_frame.shape[1] != self.width or bgr_frame.shape[0] != self.height:
                bgr_frame = cv2.resize(bgr_frame, (self.width, self.height))
            self._proc.stdin.write(bgr_frame.tobytes())
            self._frame_count += 1

    def write_text(self, lines: list[str]):
        """Write ASCII text lines to the text dump output."""
        if self.config.format == OutputFormat.TEXT_DUMP:
            if not hasattr(self, "_txt_file"):
                self._txt_file = open(self.config.output_path, "w", encoding="utf-8")
            self._txt_file.write("\n".join(lines) + "\n\n")

    def close(self) -> bool:
        """Finalise the output.  Returns True on success."""
        cfg = self.config

        # Text dump
        if hasattr(self, "_txt_file"):
            self._txt_file.close()
            return True

        # Image sequence — nothing to finalise
        if cfg.format == OutputFormat.IMAGE_SEQ:
            return True

        if self._proc is None:
            return False

        self._proc.stdin.close()
        self._proc.wait()
        ok = self._proc.returncode == 0

        # GIF post-processing
        if cfg.format == OutputFormat.GIF and ok and hasattr(self, "_gif_path"):
            ok = self._convert_avi_to_gif()

        return ok

    def _convert_avi_to_gif(self) -> bool:
        """Two-pass AVI→GIF conversion for palette-optimised output."""
        try:
            # Pass 1: palette
            subprocess.run([
                "ffmpeg", "-y",
                "-i", self._tmp_avi,
                "-vf", f"fps={self._fps},scale={self._scale}:-1:flags=lanczos,palettegen",
                self._palette,
            ], check=True, capture_output=True)

            # Pass 2: apply palette
            subprocess.run([
                "ffmpeg", "-y",
                "-i", self._tmp_avi,
                "-i", self._palette,
                "-filter_complex",
                f"fps={self._fps},scale={self._scale}:-1:flags=lanczos[x];[x][1:v]paletteuse",
                self._gif_path,
            ], check=True, capture_output=True)

            # Cleanup
            os.unlink(self._tmp_avi)
            os.unlink(self._palette)
            return True
        except subprocess.CalledProcessError:
            return False

    @property
    def frame_count(self) -> int:
        return self._frame_count


# ---------------------------------------------------------------------------
# Audio extraction / mux helper
# ---------------------------------------------------------------------------

def mux_audio(video_source: str, video_silent: str, output: str) -> bool:
    """
    Copy audio track from ``video_source`` into ``video_silent`` → ``output``.
    Returns True on success.
    """
    if not ffmpeg_available():
        return False
    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_silent,
            "-i", video_source,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output,
        ], check=True, capture_output=True, timeout=120)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
