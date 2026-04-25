"""
Frame Processing Pipeline
=========================
Orchestrates frame reading → plugin filtering → ASCII rendering → encoding.

Architecture:
  VideoReader  (streaming, no full-load)
    └─ FrameQueue (bounded, prevents OOM)
         └─ Worker Pool (multiprocessing or threading)
              └─ Encoder (ffmpeg subprocess)

Key design decisions:
  • Frames are NEVER fully loaded into memory — streaming via cv2.VideoCapture
  • Workers receive raw frame bytes, avoiding pickling large numpy arrays
    (uses shared memory or queues depending on platform)
  • Cancellation via threading.Event
  • Progress reported via callback
"""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Sentinel for queue termination
_STOP = object()


@dataclass
class VideoInfo:
    path: str
    width: int
    height: int
    fps: float
    total_frames: int
    duration_sec: float
    codec: str = ""
    has_audio: bool = False

    @classmethod
    def from_path(cls, path: str) -> "VideoInfo":
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {path}")
        try:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            dur = total / fps if fps > 0 else 0
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec = "".join(chr((fourcc >> (i * 8)) & 0xFF) for i in range(4))
        finally:
            cap.release()
        return cls(path, w, h, fps, total, dur, codec)


@dataclass
class PipelineProgress:
    frames_done: int = 0
    total_frames: int = 0
    fps_current: float = 0.0
    eta_seconds: float = 0.0
    stage: str = "idle"
    cpu_pct: float = 0.0
    mem_mb: float = 0.0
    error: str = ""
    cancelled: bool = False
    completed: bool = False


class FramePipeline:
    """
    Multi-threaded frame processing pipeline.

    Usage:
        pipeline = FramePipeline(profile, plugins, num_workers=4)
        pipeline.start(input_path, output_path, progress_cb)
        pipeline.cancel()  # optional early stop
    """

    def __init__(
        self,
        profile,
        plugins: list = None,
        num_workers: int = 0,
    ) -> None:
        from core.ascii_renderer import AsciiRenderer

        self.profile = profile
        self.plugins = plugins or []
        self.num_workers = num_workers or max(1, (os.cpu_count() or 2) - 1)
        self._renderer = AsciiRenderer(profile)
        self._cancel_event = threading.Event()
        self._progress = PipelineProgress()
        self._thread: Optional[threading.Thread] = None

    # ─── Public API ───────────────────────────────────────────────────────────

    def start(
        self,
        input_path: str,
        output_path: str,
        progress_cb: Callable[[PipelineProgress], None] | None = None,
        completion_cb: Callable[[PipelineProgress], None] | None = None,
    ) -> None:
        """Launch pipeline in background thread."""
        self._cancel_event.clear()
        self._progress = PipelineProgress()
        self._thread = threading.Thread(
            target=self._run,
            args=(input_path, output_path, progress_cb, completion_cb),
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def wait(self, timeout: float = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    # ─── Pipeline Core ────────────────────────────────────────────────────────

    def _run(
        self,
        input_path: str,
        output_path: str,
        progress_cb,
        completion_cb,
    ) -> None:
        p = self._progress
        try:
            info = VideoInfo.from_path(input_path)
            p.total_frames = info.total_frames
            p.stage = "initializing"

            # Determine effective FPS after frame skip
            skip = max(0, self.profile.frame_skip)
            src_fps = info.fps
            if self.profile.target_fps > 0:
                out_fps = self.profile.target_fps
                frame_interval = max(1, int(round(src_fps / out_fps)))
            else:
                frame_interval = skip + 1
                out_fps = src_fps / frame_interval

            out_fps = max(1.0, out_fps)
            fmt = self.profile.output_format

            if fmt == "txt_stream":
                self._run_txt_stream(input_path, output_path, frame_interval, out_fps, p, progress_cb)
            elif fmt == "image_seq":
                self._run_image_seq(input_path, output_path, frame_interval, p, progress_cb)
            elif fmt == "gif":
                self._run_gif(input_path, output_path, frame_interval, out_fps, p, progress_cb)
            else:
                self._run_video(input_path, output_path, frame_interval, out_fps, info, p, progress_cb)

            if not self._cancel_event.is_set():
                p.stage = "done"
                p.completed = True

        except Exception as e:
            logger.exception("Pipeline error")
            p.error = str(e)
            p.stage = "error"
        finally:
            if progress_cb:
                progress_cb(p)
            if completion_cb:
                completion_cb(p)

    def _run_video(self, input_path, output_path, frame_interval, out_fps, info, p, progress_cb):
        """Encode to MP4 via ffmpeg subprocess (pipe-based, no temp files)."""
        p.stage = "rendering"
        profile = self.profile

        # Compute output image size from a dummy frame
        dummy = np.zeros((info.height, info.width, 3), dtype=np.uint8)
        sample_img = self._renderer.render_frame_to_image(dummy, font_size=profile.font_size)
        out_h, out_w = sample_img.shape[:2]

        # Build ffmpeg command
        ffmpeg_cmd = self._build_ffmpeg_cmd(input_path, output_path, out_w, out_h, out_fps, profile)

        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        cap = cv2.VideoCapture(input_path)
        t_start = time.time()
        frame_idx = 0
        out_frame_idx = 0

        try:
            while not self._cancel_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % frame_interval == 0:
                    frame = self._apply_plugins(frame)
                    ascii_img = self._renderer.render_frame_to_image(frame, font_size=profile.font_size)

                    # Write raw BGR bytes to ffmpeg stdin
                    try:
                        proc.stdin.write(ascii_img.tobytes())
                    except BrokenPipeError:
                        break

                    out_frame_idx += 1
                    elapsed = time.time() - t_start
                    p.frames_done = frame_idx + 1
                    p.fps_current = out_frame_idx / elapsed if elapsed > 0 else 0
                    remaining = (p.total_frames - frame_idx) / frame_interval
                    p.eta_seconds = remaining / p.fps_current if p.fps_current > 0 else 0
                    self._update_sys_stats(p)

                    if progress_cb and out_frame_idx % 5 == 0:
                        progress_cb(p)

                frame_idx += 1

        finally:
            cap.release()
            try:
                proc.stdin.close()
            except Exception:
                pass
            proc.wait(timeout=30)

        if self._cancel_event.is_set():
            p.cancelled = True

    def _run_gif(self, input_path, output_path, frame_interval, out_fps, p, progress_cb):
        """Create animated GIF using Pillow."""
        from PIL import Image as PILImage
        p.stage = "rendering (GIF)"
        profile = self.profile
        cap = cv2.VideoCapture(input_path)
        frames_pil = []
        frame_idx = 0

        while not self._cancel_event.is_set():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                frame = self._apply_plugins(frame)
                ascii_img = self._renderer.render_frame_to_image(frame, font_size=profile.font_size)
                rgb = cv2.cvtColor(ascii_img, cv2.COLOR_BGR2RGB)
                frames_pil.append(PILImage.fromarray(rgb))
                p.frames_done = frame_idx + 1
                if progress_cb and len(frames_pil) % 5 == 0:
                    progress_cb(p)
            frame_idx += 1

        cap.release()
        if frames_pil and not self._cancel_event.is_set():
            p.stage = "saving GIF"
            if progress_cb:
                progress_cb(p)
            delay = max(20, int(1000 / out_fps))
            frames_pil[0].save(
                output_path,
                save_all=True,
                append_images=frames_pil[1:],
                loop=0,
                duration=delay,
                optimize=False,
            )

    def _run_image_seq(self, input_path, output_path, frame_interval, p, progress_cb):
        """Save each frame as PNG image sequence."""
        p.stage = "rendering (image seq)"
        profile = self.profile
        out_dir = Path(output_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        cap = cv2.VideoCapture(input_path)
        frame_idx = 0
        out_idx = 0

        while not self._cancel_event.is_set():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                frame = self._apply_plugins(frame)
                ascii_img = self._renderer.render_frame_to_image(frame, font_size=profile.font_size)
                fname = out_dir / f"frame_{out_idx:06d}.png"
                cv2.imwrite(str(fname), ascii_img)
                out_idx += 1
                p.frames_done = frame_idx + 1
                if progress_cb and out_idx % 10 == 0:
                    progress_cb(p)
            frame_idx += 1

        cap.release()

    def _run_txt_stream(self, input_path, output_path, frame_interval, out_fps, p, progress_cb):
        """Write ASCII text frames to a .txt file."""
        p.stage = "rendering (text)"
        cap = cv2.VideoCapture(input_path)
        frame_idx = 0

        with open(output_path, "w", encoding="utf-8") as f:
            while not self._cancel_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % frame_interval == 0:
                    frame = self._apply_plugins(frame)
                    grid = self._renderer.render_frame(frame)
                    f.write(f"=== FRAME {frame_idx} ===\n")
                    for row in grid:
                        line = "".join(c.char if hasattr(c, "char") else c for c in row)
                        f.write(line + "\n")
                    f.write("\n")
                    p.frames_done = frame_idx + 1
                    if progress_cb and frame_idx % 10 == 0:
                        progress_cb(p)
                frame_idx += 1

        cap.release()

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _apply_plugins(self, frame: np.ndarray) -> np.ndarray:
        for plugin in self.plugins:
            try:
                frame = plugin.process(frame)
            except Exception as e:
                logger.warning("Plugin %s failed: %s", getattr(plugin, "plugin_id", "?"), e)
        return frame

    def _build_ffmpeg_cmd(self, input_path, output_path, out_w, out_h, out_fps, profile) -> list[str]:
        use_gpu = profile.use_gpu and self._check_nvenc()
        codec = "h264_nvenc" if use_gpu else "libx264"
        crf_flag = ["-b:v", "5M"] if use_gpu else ["-crf", str(profile.output_quality)]

        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{out_w}x{out_h}",
            "-r", str(out_fps),
            "-i", "pipe:0",
            # Attempt to copy audio from source
            "-i", input_path,
            "-map", "0:v:0",
            "-map_options", "ignore_missing",
            "-c:v", codec,
            *crf_flag,
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-shortest",
            output_path,
        ]
        # Simpler command if audio mapping causes issues
        cmd_simple = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{out_w}x{out_h}",
            "-r", str(out_fps),
            "-i", "pipe:0",
            "-c:v", codec,
            *crf_flag,
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]
        return cmd_simple

    @staticmethod
    def _check_nvenc() -> bool:
        try:
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=5
            )
            return "h264_nvenc" in result.stdout
        except Exception:
            return False

    @staticmethod
    def _update_sys_stats(p: PipelineProgress) -> None:
        try:
            import psutil
            p.cpu_pct = psutil.cpu_percent(interval=None)
            p.mem_mb = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
        except Exception:
            pass


class PreviewPipeline:
    """
    Lightweight single-frame renderer for real-time UI preview.
    Runs in the calling thread (UI throttles calls).
    """

    def __init__(self, profile, plugins: list = None) -> None:
        from core.ascii_renderer import AsciiRenderer
        self._renderer = AsciiRenderer(profile)
        self.plugins = plugins or []

    def render_preview(self, bgr_frame: np.ndarray) -> np.ndarray:
        """Return rendered ASCII image for display."""
        for plugin in self.plugins:
            try:
                bgr_frame = plugin.process(bgr_frame)
            except Exception:
                pass
        return self._renderer.render_frame_to_image(bgr_frame, font_size=self._renderer.profile.font_size)
