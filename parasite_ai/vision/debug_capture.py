"""
parasite_ai/vision/debug_capture.py - Per-step Diagnostic Screenshot Recorder.

Saves annotated pre-action and clean post-action desktop frames to disk
(<data_dir>/screenshots/<timestamp>_<goal_slug>/step_XX_pre.jpg & step_XX_post.jpg)
purely for human post-mortem debugging. Never mutates the live perception frame
passed to the VLM or vision pipeline.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _slugify_goal(goal: str, max_len: int = 36) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", (goal or "").strip().lower()).strip("_")
    return (cleaned[:max_len].strip("_") or "episode")


class DebugScreenshotRecorder:
    """Writes annotated per-step diagnostic screenshots with bounded episode retention."""

    def __init__(
        self,
        base_dir: Path | str = Path("data"),
        enabled: bool = True,
        max_episodes: int = 20,
        jpeg_quality: int = 88,
    ) -> None:
        self.screenshots_root = Path(base_dir) / "screenshots"
        is_pytest_default_dir = bool(os.environ.get("PYTEST_CURRENT_TEST")) and Path(base_dir) == Path("data")
        self.enabled = bool(enabled) and not is_pytest_default_dir
        self.max_episodes = max(1, int(max_episodes))
        self.jpeg_quality = max(50, min(100, int(jpeg_quality)))
        self.current_episode_dir: Optional[Path] = None
        self.step_counter: int = 0

    def start_episode(self, goal: str = "", episode_id: Optional[str] = None) -> Optional[Path]:
        """Creates a new episode screenshot folder and prunes oldest folders beyond retention."""
        if not self.enabled:
            return None
        try:
            self.screenshots_root.mkdir(parents=True, exist_ok=True)
            stamp = episode_id or datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = _slugify_goal(goal)
            candidate = self.screenshots_root / f"{stamp}_{slug}"
            if candidate.exists():
                candidate = self.screenshots_root / f"{stamp}_{int(time.time() * 1000) % 1000:03d}_{slug}"
            candidate.mkdir(parents=True, exist_ok=True)
            self.current_episode_dir = candidate
            self.step_counter = 0
            self._prune_old_episodes()
            return candidate
        except Exception as exc:
            logger.debug("Could not initialize debug screenshot episode directory: %s", exc)
            return None

    def _prune_old_episodes(self) -> None:
        """Removes oldest episode folders beyond max_episodes."""
        try:
            dirs = [p for p in self.screenshots_root.iterdir() if p.is_dir()]
            if len(dirs) <= self.max_episodes:
                return
            dirs.sort(key=lambda p: p.stat().st_mtime)
            for old_dir in dirs[: len(dirs) - self.max_episodes]:
                shutil.rmtree(old_dir, ignore_errors=True)
        except Exception as exc:
            logger.debug("Screenshot retention pruning skipped: %s", exc)

    @staticmethod
    def _to_bgr(frame: np.ndarray) -> np.ndarray:
        """Converts ScreenCapture RGB/RGBA/Grayscale frames into OpenCV BGR."""
        if frame.ndim == 2:
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        if frame.shape[2] == 4:
            return cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
        if frame.shape[2] == 3:
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        return frame.copy()

    @staticmethod
    def _annotate_pre_frame(
        frame: np.ndarray,
        step_idx: int,
        raw_coords: Optional[Tuple[int, int]],
        final_coords: Optional[Tuple[int, int]],
        snap_strategy: Optional[str],
        matched_label: Optional[str],
        optical_tier: Optional[str],
        active_window: Optional[str],
        action_label: Optional[str],
        thought: Optional[str],
        burst_coords: Optional[List[Tuple[int, int]]] = None,
    ) -> np.ndarray:
        """Draws human-only diagnostic overlays onto a copy of pre_frame."""
        canvas = DebugScreenshotRecorder._to_bgr(frame)

        h, w = canvas.shape[:2]

        def _draw_crosshair(pt: Tuple[int, int], color: Tuple[int, int, int], radius: int = 14) -> None:
            px, py = int(pt[0]), int(pt[1])
            if not (0 <= px < w and 0 <= py < h):
                return
            cv2.circle(canvas, (px, py), radius, color, 2, lineType=cv2.LINE_AA)
            cv2.line(canvas, (max(0, px - radius - 6), py), (min(w - 1, px + radius + 6), py), color, 1, lineType=cv2.LINE_AA)
            cv2.line(canvas, (px, max(0, py - radius - 6)), (px, min(h - 1, py + radius + 6)), color, 1, lineType=cv2.LINE_AA)

        if burst_coords:
            for b_i, b_pt in enumerate(burst_coords, start=1):
                _draw_crosshair(b_pt, (0, 255, 128), radius=10)
                bx, by = int(b_pt[0]), int(b_pt[1])
                cv2.putText(canvas, str(b_i), (bx + 8, by - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 128), 1, cv2.LINE_AA)
        else:
            if raw_coords is not None:
                _draw_crosshair(raw_coords, (0, 0, 255), radius=16)  # Red: raw VLM coordinate

            if final_coords is not None:
                _draw_crosshair(final_coords, (0, 255, 0), radius=11)  # Green: final dispatched coordinate
                if raw_coords is not None and tuple(raw_coords) != tuple(final_coords):
                    cv2.arrowedLine(
                        canvas,
                        (int(raw_coords[0]), int(raw_coords[1])),
                        (int(final_coords[0]), int(final_coords[1])),
                        (0, 255, 255),
                        2,
                        tipLength=0.25,
                        line_type=cv2.LINE_AA,
                    )

        # Compact top HUD banner for human debugging
        banner_h = min(52, h)
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (w, banner_h), (15, 15, 18), -1)
        cv2.addWeighted(overlay, 0.72, canvas, 0.28, 0, canvas)

        coord_part = ""
        if raw_coords is not None and final_coords is not None:
            coord_part = f" | {raw_coords}->{final_coords}" if tuple(raw_coords) != tuple(final_coords) else f" | {final_coords}"
        elif final_coords is not None:
            coord_part = f" | {final_coords}"

        strat_parts = [p for p in (snap_strategy if snap_strategy and snap_strategy != "none" else None, optical_tier) if p]
        strat_str = f" [{'+'.join(strat_parts)}]" if strat_parts else ""
        lbl_str = f" '{matched_label[:22]}'" if matched_label else ""
        win_str = f" | Win: {active_window[:32]}" if active_window else ""
        line1 = f"Step {step_idx:02d} | {action_label or 'ACTION'}{coord_part}{strat_str}{lbl_str}{win_str}"
        cv2.putText(canvas, line1[:150], (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (240, 240, 240), 1, cv2.LINE_AA)

        if thought:
            clean_thought = " ".join(str(thought).split())
            cv2.putText(canvas, clean_thought[:160], (10, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (180, 225, 255), 1, cv2.LINE_AA)

        return canvas

    def save_step_frames(
        self,
        pre_frame: Optional[np.ndarray],
        post_frame: Optional[np.ndarray] = None,
        step_idx: Optional[int] = None,
        raw_coords: Optional[Tuple[int, int]] = None,
        final_coords: Optional[Tuple[int, int]] = None,
        snap_strategy: Optional[str] = None,
        matched_label: Optional[str] = None,
        optical_tier: Optional[str] = None,
        active_window: Optional[str] = None,
        action_label: Optional[str] = None,
        thought: Optional[str] = None,
        is_sensitive: bool = False,
        burst_frames: Optional[List[np.ndarray]] = None,
        burst_coords: Optional[List[Tuple[int, int]]] = None,
    ) -> Optional[Path]:
        """Saves annotated pre_frame and clean post_frame to the active episode directory."""
        if not self.enabled or is_sensitive or pre_frame is None:
            return None
        if not isinstance(pre_frame, np.ndarray) or pre_frame.size == 0:
            return None

        try:
            if self.current_episode_dir is None:
                self.start_episode()
            if self.current_episode_dir is None:
                return None

            if step_idx is None:
                self.step_counter += 1
                step_num = self.step_counter
            else:
                step_num = int(step_idx)
                self.step_counter = max(self.step_counter, step_num)

            annotated_pre = self._annotate_pre_frame(
                frame=pre_frame,
                step_idx=step_num,
                raw_coords=raw_coords,
                final_coords=final_coords,
                snap_strategy=snap_strategy,
                matched_label=matched_label,
                optical_tier=optical_tier,
                active_window=active_window,
                action_label=action_label,
                thought=thought,
                burst_coords=burst_coords,
            )
            pre_path = self.current_episode_dir / f"step_{step_num:02d}_pre.jpg"
            cv2.imwrite(str(pre_path), annotated_pre, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])

            if burst_frames:
                for b_idx, b_frame in enumerate(burst_frames, start=1):
                    if isinstance(b_frame, np.ndarray) and b_frame.size > 0:
                        b_out = self._to_bgr(b_frame)
                        b_path = self.current_episode_dir / f"step_{step_num:02d}_post_{b_idx:02d}.jpg"
                        cv2.imwrite(str(b_path), b_out, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])

            if post_frame is not None and isinstance(post_frame, np.ndarray) and post_frame.size > 0:
                post_out = self._to_bgr(post_frame)
                post_path = self.current_episode_dir / f"step_{step_num:02d}_post.jpg"
                cv2.imwrite(str(post_path), post_out, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])

            return pre_path
        except Exception as exc:
            logger.debug("Failed to save debug step screenshot: %s", exc)
            return None
