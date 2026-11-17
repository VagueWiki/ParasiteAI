"""
parasite_ai/mind/app_memory.py - Persistent SQLite WAL AppMemory & Farmed-Plan Cache.

Provides:
- Layer 1.5 farmed-plan caching (exact normalized goal match, version-gated, failure-evicted)
- Verified OS app profile tracking (§8: process_name, last_window_title, launch stats only)
- Episode telemetry persistence (including fast_path_steps)
- Zero-Gemini promotion candidate selection for directive-complete farmed plans -> draft SKILL.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
import threading
from typing import List, Optional, Tuple

import parasite_ai
from parasite_ai.config import AppMemoryConfig
from parasite_ai.mind.parasite_protocol import ParasitePlan
from parasite_ai.safety.content_scanner import sanitize_or_reject

_PUNCT_TAIL_RE = re.compile(r"[.!?,;:]+$")
_WS_RE = re.compile(r"\s+")


def normalize_goal(goal: str) -> str:
    """Normalizes a user goal for exact-match Layer 1.5 cache lookup."""
    collapsed = _WS_RE.sub(" ", (goal or "").strip().lower())
    return _PUNCT_TAIL_RE.sub("", collapsed).strip()


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _version_prefix(version: str) -> str:
    parts = (version or "").strip().split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else (version or "").strip()


class AppMemory:
    """Thread-safe SQLite WAL persistent memory for farmed plans, OS app profiles, and episodes."""

    def __init__(
        self,
        config: Optional[AppMemoryConfig] = None,
        app_version: Optional[str] = None,
    ) -> None:
        self.config = config or AppMemoryConfig(enabled=True)
        self.app_version = app_version or getattr(parasite_ai, "__version__", "0.4.5.3")
        self._lock = threading.RLock()

        db_path_str = str(self.config.db_path)
        if db_path_str != ":memory:":
            Path(db_path_str).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path_str, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS farmed_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_norm TEXT NOT NULL,
                    selected_program TEXT NOT NULL DEFAULT '',
                    plan_json TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'proactive',
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    promoted_skill_id TEXT,
                    app_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT NOT NULL,
                    UNIQUE(goal_norm, selected_program)
                );

                CREATE TABLE IF NOT EXISTS app_profiles (
                    process_name TEXT PRIMARY KEY,
                    last_window_title TEXT NOT NULL DEFAULT '',
                    launch_count INTEGER NOT NULL DEFAULT 0,
                    last_launch_ok INTEGER NOT NULL DEFAULT 1,
                    last_seen_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL,
                    plan_source TEXT NOT NULL,
                    plan_ref TEXT,
                    success INTEGER NOT NULL,
                    exit_reason TEXT NOT NULL,
                    steps INTEGER NOT NULL DEFAULT 0,
                    duration_sec REAL NOT NULL DEFAULT 0.0,
                    fast_path_steps INTEGER NOT NULL DEFAULT 0,
                    app_version TEXT NOT NULL,
                    ended_at TEXT NOT NULL
                );
                """
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def journal_mode(self) -> str:
        with self._lock:
            row = self._conn.execute("PRAGMA journal_mode;").fetchone()
            return str(row[0]).lower() if row else ""

    def store_farmed_plan(
        self,
        goal: str,
        plan: ParasitePlan,
        source: str = "proactive",
    ) -> int:
        """Stores or refreshes a farmed ParasitePlan (starts with 0 successes until verified)."""
        goal_scan = sanitize_or_reject(goal or "")
        if not goal_scan.allowed:
            raise ValueError(f"Farmed plan goal rejected by ContentScanner: {goal_scan.reason}")

        raw_json = plan.model_dump_json()
        plan_scan = sanitize_or_reject(raw_json)
        if not plan_scan.allowed:
            raise ValueError(f"Farmed plan rejected by ContentScanner: {plan_scan.reason}")

        if plan_scan.redacted_count > 0:
            clean_plan = ParasitePlan.model_validate_json(plan_scan.text)
            plan_json = clean_plan.model_dump_json()
            prog = (clean_plan.selected_program or "").strip()
        else:
            plan_json = raw_json
            prog = (plan.selected_program or "").strip()

        goal_norm = normalize_goal(goal_scan.text)
        now = _utc_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO farmed_plans (
                    goal_norm, selected_program, plan_json, source,
                    success_count, failure_count, consecutive_failures,
                    promoted_skill_id, app_version, created_at, last_used_at
                ) VALUES (?, ?, ?, ?, 0, 0, 0, NULL, ?, ?, ?)
                ON CONFLICT(goal_norm, selected_program) DO UPDATE SET
                    plan_json = excluded.plan_json,
                    source = excluded.source,
                    consecutive_failures = 0,
                    app_version = excluded.app_version,
                    last_used_at = excluded.last_used_at
                """,
                (goal_norm, prog, plan_json, source, self.app_version, now, now),
            )
            row = self._conn.execute(
                "SELECT id FROM farmed_plans WHERE goal_norm = ? AND selected_program = ?",
                (goal_norm, prog),
            ).fetchone()
            self._conn.commit()
            return int(row["id"])

    def lookup_farmed_plan(
        self,
        goal: str,
        active_process: Optional[str] = None,
    ) -> Optional[Tuple[int, ParasitePlan]]:
        """Returns (plan_id, ParasitePlan) for an eligible cached plan, or None."""
        goal_norm = normalize_goal(goal)
        if not goal_norm:
            return None
        ver_prefix = _version_prefix(self.app_version)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, selected_program, plan_json, app_version
                FROM farmed_plans
                WHERE goal_norm = ?
                  AND success_count >= 1
                  AND consecutive_failures < ?
                ORDER BY success_count DESC, id DESC
                """,
                (goal_norm, self.config.max_consecutive_failures),
            ).fetchall()

        active_low = (active_process or "").strip().lower()
        matching_rows: List[sqlite3.Row] = []
        for r in rows:
            if _version_prefix(str(r["app_version"])) == ver_prefix:
                matching_rows.append(r)

        if not matching_rows:
            return None

        # Prefer a plan whose selected_program hints at active_process if available
        chosen = matching_rows[0]
        if active_low:
            stem = active_low.removesuffix(".exe")
            for r in matching_rows:
                if stem and stem in str(r["selected_program"]).lower():
                    chosen = r
                    break

        try:
            plan = ParasitePlan.model_validate_json(chosen["plan_json"])
        except Exception:
            return None
        return int(chosen["id"]), plan

    def record_outcome(self, plan_id: int, success: bool) -> None:
        now = _utc_iso()
        with self._lock:
            if success:
                self._conn.execute(
                    """
                    UPDATE farmed_plans
                    SET success_count = success_count + 1,
                        consecutive_failures = 0,
                        last_used_at = ?
                    WHERE id = ?
                    """,
                    (now, plan_id),
                )
            else:
                self._conn.execute(
                    """
                    UPDATE farmed_plans
                    SET failure_count = failure_count + 1,
                        consecutive_failures = consecutive_failures + 1,
                        last_used_at = ?
                    WHERE id = ?
                    """,
                    (now, plan_id),
                )
            self._conn.commit()

    def record_app_seen(
        self,
        process_name: str,
        window_title: str = "",
        launch_ok: bool = True,
    ) -> None:
        proc = (process_name or "").strip().lower()
        if not proc:
            return
        now = _utc_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO app_profiles (process_name, last_window_title, launch_count, last_launch_ok, last_seen_at)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(process_name) DO UPDATE SET
                    last_window_title = CASE
                        WHEN excluded.last_window_title != '' THEN excluded.last_window_title
                        ELSE app_profiles.last_window_title
                    END,
                    launch_count = app_profiles.launch_count + 1,
                    last_launch_ok = excluded.last_launch_ok,
                    last_seen_at = excluded.last_seen_at
                """,
                (proc, (window_title or "")[:200], 1 if launch_ok else 0, now),
            )
            self._conn.commit()

    def get_last_process(self, program_hint: str) -> Optional[str]:
        """Resolves a discovered/cached OS executable name from ``app_profiles``."""
        hint = (program_hint or "").strip().lower()
        if not hint:
            return None
        hint_stem = re.sub(r"\.exe$", "", hint)
        tokens = [t for t in re.findall(r"[a-z0-9]+", hint_stem) if len(t) >= 2]

        with self._lock:
            rows = self._conn.execute(
                """
                SELECT process_name, last_window_title
                FROM app_profiles
                ORDER BY last_launch_ok DESC, launch_count DESC, last_seen_at DESC
                """
            ).fetchall()

        if not rows:
            return None

        # Pass 1: exact process match
        for row in rows:
            proc_low = str(row["process_name"] or "").strip().lower()
            if proc_low and (proc_low == hint or proc_low == f"{hint_stem}.exe"):
                return str(row["process_name"])

        # Pass 2: stem substring or full token coverage across process/title
        for row in rows:
            proc_raw = str(row["process_name"] or "").strip()
            proc_low = proc_raw.lower()
            proc_stem = proc_low.removesuffix(".exe")
            title_low = str(row["last_window_title"] or "").lower()
            if not proc_low:
                continue
            if len(hint_stem) >= 3 and (hint_stem in proc_stem or proc_stem in hint_stem):
                return proc_raw
            if tokens and all(tok in proc_low or tok in title_low for tok in tokens):
                return proc_raw

        # Pass 3: partial significant token match
        sig_tokens = [t for t in tokens if len(t) >= 3]
        if sig_tokens:
            for row in rows:
                proc_raw = str(row["process_name"] or "").strip()
                proc_stem = proc_raw.lower().removesuffix(".exe")
                title_low = str(row["last_window_title"] or "").lower()
                if proc_stem and any(tok in proc_stem or tok in title_low for tok in sig_tokens):
                    return proc_raw

        return None

    def record_episode(
        self,
        goal: str,
        plan_source: str,
        plan_ref: Optional[str],
        success: bool,
        exit_reason: str,
        steps: int,
        duration_sec: float,
        fast_path_steps: int = 0,
    ) -> int:
        now = _utc_iso()
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO episodes (
                    goal, plan_source, plan_ref, success, exit_reason,
                    steps, duration_sec, fast_path_steps, app_version, ended_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    goal,
                    plan_source,
                    plan_ref,
                    1 if success else 0,
                    exit_reason,
                    steps,
                    float(duration_sec),
                    int(fast_path_steps),
                    self.app_version,
                    now,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid or 0)

    def promotion_candidates(
        self,
        min_successes: Optional[int] = None,
    ) -> List[Tuple[int, str, ParasitePlan]]:
        """Returns cached plans ready for zero-Gemini draft SKILL.md promotion."""
        threshold = (
            min_successes
            if min_successes is not None
            else self.config.promote_after_successes
        )
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, goal_norm, plan_json
                FROM farmed_plans
                WHERE success_count >= ?
                  AND promoted_skill_id IS NULL
                  AND consecutive_failures < ?
                ORDER BY id ASC
                """,
                (threshold, self.config.max_consecutive_failures),
            ).fetchall()

        candidates: List[Tuple[int, str, ParasitePlan]] = []
        for r in rows:
            try:
                plan = ParasitePlan.model_validate_json(r["plan_json"])
            except Exception:
                continue
            if plan.steps and all(s.action is not None for s in plan.steps):
                candidates.append((int(r["id"]), str(r["goal_norm"]), plan))
        return candidates

    def mark_promoted(self, plan_id: int, skill_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE farmed_plans SET promoted_skill_id = ? WHERE id = ?",
                (skill_id, plan_id),
            )
            self._conn.commit()
