"""
tests/test_challenger_m4e_precision.py - Adversarial Stress Test Suite for Milestone 4E.

Empirical Challenger verification for:
1. Substring Collision Invariants (0.0 false click score guarantee across 270+ individual collision attacks)
2. Negative Verb Traps (160+ destructive verb permutations unconditionally zeroed)
3. Word Boundary & Exact Matching Matrix (Exact 1.0, Prefix 0.95, Word Boundary 0.80..0.90)
4. Noisy OCR, Unicode, Em-dashes, Emojis, and ReDoS Injection Resilience
5. UIElement Role Filtering, Thresholding, and High-Volume Candidate Selection
6. UniversalAppResolver 3-Tier State Machine Progression and Loop-Free Exhaustion
"""

from __future__ import annotations

import re
import threading
import time
from typing import List, Optional
import pytest

from parasite_ai.mind.memory import ActionPlan, ActionType
from parasite_ai.mind.resolver import PrecisionAppMatcher, UniversalAppResolver
from parasite_ai.ui.types import UIElement


# ===========================================================================
# 1. Substring Collision Invariant Dataset (270 Individual Collision Pairs)
# ===========================================================================

SUBSTRING_COLLISION_DATASET = [
    # Target "art" (50 collision candidates)
    ("art", [
        "SmartScreen", "catalog", "Restart", "Chart", "Dart", "Bystander",
        "Part", "Party", "Tart", "Earth", "Heart", "Cart", "Department",
        "Start", "Starting", "Startup", "Article", "Artifact", "Partner",
        "Apartment", "Martyr", "Charter", "Quarterly", "SmartCard", "SmartArt",
        "Artisan", "Mozart", "Wart", "Clipart", "Wartime", "Sweetheart",
        "Rampart", "Heartbeat", "Restarted", "Restarting", "Disembark",
        "Partial", "Particle", "Particular", "Departure", "Compartment",
        "Cartridge", "Cartographer", "Tartar", "Dartboard", "Bystanders",
        "Flowchart", "Barcode", "SmartHome", "SmartTV",
    ]),
    # Target "cat" (50 collision candidates)
    ("cat", [
        "catalog", "catalogue", "scatter", "indicate", "application", "locate",
        "location", "catch", "category", "certificate", "concatenate",
        "duplicate", "replicate", "vacation", "education", "syndicate",
        "abdicate", "dedication", "communication", "notification", "justification",
        "classification", "qualification", "specification", "modification",
        "verification", "amplification", "clarification", "simplification",
        "identification", "authentication", "eradication", "allocation",
        "dislocation", "relocation", "vocation", "altercation", "fabrication",
        "lubrication", "intoxication", "confiscation", "defecation", "suffocating",
        "scattered", "scatterplot", "catchment", "catering", "catacomb",
        "catalyst", "caterpillar",
    ]),
    # Target "edit" (40 collision candidates)
    ("edit", [
        "credit", "expedite", "hereditary", "sedition", "editor", "edition",
        "auditing", "meditation", "predator", "discredit", "accredit",
        "remeditation", "credibility", "creditor", "creditable", "expeditious",
        "expediter", "extradition", "periodicity", "credenza", "incredible",
        "incredulous", "heredity", "subreddit", "coedit", "inedible", "bedlam",
        "obedience", "rediscovery", "sedimentation", "editorial", "editorship",
        "credentials", "credentialing", "accreditation", "accredited",
        "discrediting", "meditative", "expedition", "predatory",
    ]),
    # Target "calc" (30 collision candidates)
    ("calc", [
        "Recalculate", "Decalcify", "Calcite", "Calcium", "Incalculable",
        "Calculus", "Calculator", "Calculating", "Calculated", "Calculation",
        "Calcify", "Calcification", "Recalculation", "Calcareous", "Calcined",
        "Descaling", "Decal", "Fiscal", "Recall", "Escalator", "Focal",
        "Locally", "Medical", "Typical", "Critical", "Musical", "Radically",
        "Optical", "Fiscally", "Recalled",
    ]),
    # Target "pad" (20 collision candidates)
    ("pad", [
        "keypad", "touchpad", "launchpad", "trackpad", "spade", "padding",
        "padlocked", "footpad", "notepad", "toad", "roadpad", "bipad",
        "tripad", "nonpadding", "paddle", "paddock", "padded", "padlock",
        "spades", "touchpads",
    ]),
    # Target "word" (20 collision candidates)
    ("word", [
        "password", "sword", "crossword", "foreword", "afterword", "catchword",
        "swordfish", "awkward", "standard", "backward", "forward", "wording",
        "wordsmith", "coward", "reward", "headword", "passwordless",
        "backwards", "forwards", "passwords",
    ]),
    # Target "code" (20 collision candidates)
    ("code", [
        "encode", "decode", "transcode", "barcode", "passcode", "zipcode",
        "geocode", "opcode", "unicode", "codex", "codify", "codename",
        "coder", "decoding", "encoding", "barcodes", "passcodes", "zipcodes",
        "transcoding", "coders",
    ]),
    # Target "paint" (15 collision candidates)
    ("paint", [
        "repaint", "painting", "painter", "painstaking", "pinpoint",
        "complaint", "restraint", "acquainted", "faint", "repainted",
        "painters", "paintings", "complaints", "restraints", "fainted",
    ]),
    # Target "fox" (10 collision candidates)
    ("fox", [
        "firefox", "outfox", "orthodox", "paradox", "outfoxed",
        "unorthodox", "paradoxical", "orthodoxies", "paradoxes", "outfoxing",
    ]),
    # Target "note" (15 collision candidates)
    ("note", [
        "notepad", "notebook", "footnote", "keynote", "denoted",
        "connotation", "denote", "knotty", "notepads", "notebooks",
        "footnotes", "keynotes", "denoting", "connotations", "annotated",
    ]),
]

FLATTENED_COLLISIONS = [
    (target, label)
    for target, labels in SUBSTRING_COLLISION_DATASET
    for label in labels
]


class TestSubstringCollisionInvariants:
    """
    Stress-tests the 0.0 false click invariant against non-boundary substring containment.
    Verifies 270 distinct adversarial collision pairs individually.
    """

    @pytest.mark.parametrize("target, label", FLATTENED_COLLISIONS)
    def test_individual_substring_collision_scores_zero(self, target: str, label: str) -> None:
        """Every individual non-boundary substring occurrence must score 0.0."""
        score = PrecisionAppMatcher.score_match(label, target)
        assert score == 0.0, (
            f"SUBSTRING COLLISION DETECTED: label='{label}' matched target='{target}' "
            f"with score {score} (expected 0.0)"
        )


# ===========================================================================
# 2. Negative Verb Traps (160+ Permutations)
# ===========================================================================

NEGATIVE_VERBS = ["exit", "close", "quit", "cancel", "uninstall", "delete", "remove", "kill"]
SAMPLE_TARGETS = ["notepad", "calculator", "chrome", "spotify", "code", "terminal"]


class TestNegativeVerbTraps:
    """
    Verifies that any negative/destructive verb completely zeroes the matching score (0.0).
    """

    @pytest.mark.parametrize("verb", NEGATIVE_VERBS)
    @pytest.mark.parametrize("target", SAMPLE_TARGETS)
    def test_prefix_negative_verb(self, verb: str, target: str) -> None:
        """'{verb} {target}' must score 0.0."""
        label = f"{verb.title()} {target.title()}"
        score = PrecisionAppMatcher.score_match(label, target)
        assert score == 0.0, f"Failed for '{label}': expected 0.0, got {score}"

    @pytest.mark.parametrize("verb", NEGATIVE_VERBS)
    @pytest.mark.parametrize("target", SAMPLE_TARGETS)
    def test_postfix_negative_verb(self, verb: str, target: str) -> None:
        """'{target} {verb}' must score 0.0."""
        label = f"{target.title()} {verb.title()}"
        score = PrecisionAppMatcher.score_match(label, target)
        assert score == 0.0, f"Failed for '{label}': expected 0.0, got {score}"

    @pytest.mark.parametrize("verb", NEGATIVE_VERBS)
    @pytest.mark.parametrize("target", ["notepad", "calculator"])
    @pytest.mark.parametrize("template", [
        "{verb}-{target}",
        "{verb}_{target}",
        "{verb}: {target}",
        "{verb} - {target}",
        "{verb} / {target}",
        "{verb} ({target})",
        "{target} [{verb}]",
        "{verb_upper} {target_upper}",
        "cLoSe_{target}",
        "Do you want to {verb} {target}?",
        "Click here to {verb} {target}",
        "Force {verb} {target} process",
    ])
    def test_negative_verb_punctuation_and_sentence_variants(
        self, verb: str, target: str, template: str
    ) -> None:
        """Negative verbs with various separators, casings, and sentence contexts must score 0.0."""
        label = template.format(
            verb=verb,
            target=target,
            verb_upper=verb.upper(),
            target_upper=target.upper(),
        )
        score = PrecisionAppMatcher.score_match(label, target)
        assert score == 0.0, f"Failed for template '{label}': got {score}"


# ===========================================================================
# 3. Word Boundary & Exact Matching Matrix
# ===========================================================================

class TestBoundaryAndExactMatching:
    """
    Verifies exact matching (1.0), prefix boundaries (0.95), and word boundaries (0.80..0.90).
    """

    @pytest.mark.parametrize("app_name", [
        "Notepad", "Calculator", "Spotify", "Discord",
        "Visual Studio Code", "Windows Terminal", "Google Chrome",
        "Adobe Acrobat Reader", "Microsoft Edge", "File Explorer",
        "Task Manager", "cmd.exe", "powershell.exe", "Paint.NET",
    ])
    def test_exact_matches_score_1_0(self, app_name: str) -> None:
        """Exact matches (case-insensitive and trimmed) score 1.0."""
        assert PrecisionAppMatcher.score_match(app_name, app_name) == 1.0
        assert PrecisionAppMatcher.score_match(app_name.lower(), app_name.upper()) == 1.0
        assert PrecisionAppMatcher.score_match(f"  {app_name}  \t", app_name) == 1.0

    @pytest.mark.parametrize("target, label", [
        ("notepad", "Notepad - Untitled"),
        ("notepad", "Notepad: Document Editor"),
        ("notepad", "Notepad (32-bit)"),
        ("notepad", "Notepad App"),
        ("calculator", "Calculator - Standard"),
        ("calculator", "Calculator: Scientific Mode"),
        ("code", "Code - Workspace 1"),
    ])
    def test_prefix_boundary_scores_0_95(self, target: str, label: str) -> None:
        """Prefix followed by space, hyphen, colon scores 0.95."""
        assert PrecisionAppMatcher.score_match(label, target) == 0.95

    @pytest.mark.parametrize("target, label", [
        ("notepad", "Open Notepad"),
        ("notepad", "Launch Microsoft Notepad Now"),
        ("notepad", "&Notepad"),
        ("notepad", "\"Notepad\""),
        ("notepad", "[Notepad]"),
        ("code", "Visual Studio Code"),
        ("paint", "Paint.NET"),
    ])
    def test_word_boundary_scores_above_threshold(self, target: str, label: str) -> None:
        """Legitimate word boundary occurrences must score >= 0.80."""
        score = PrecisionAppMatcher.score_match(label, target)
        assert 0.80 <= score <= 0.95, f"Expected 0.80 <= score <= 0.95 for '{label}', got {score}"

    def test_positional_decay_ranking(self) -> None:
        """Earlier occurrences in the label string rank higher than later occurrences."""
        target = "notepad"
        label_early = "Notepad Text Editor"
        label_late = "A very long detailed application window description with Notepad"

        score_early = PrecisionAppMatcher.score_match(label_early, target)
        score_late = PrecisionAppMatcher.score_match(label_late, target)

        assert score_early > score_late
        assert score_early >= 0.80
        assert score_late >= 0.80


# ===========================================================================
# 4. Noisy Labels, Unicode, ReDoS, and Boundary Anomaly Resilience
# ===========================================================================

class TestLabelAnomalyResilience:
    """
    Stress-tests malformed, noisy, Unicode, accented, and adversarial injection strings.
    """

    @pytest.mark.parametrize("target, label", [
        ("", ""),
        ("   ", "   "),
        ("notepad", ""),
        ("", "notepad"),
        ("notepad", "   "),
        ("   ", "notepad"),
        ("notepad", "..."),
        ("notepad", ":::"),
        ("notepad", "---"),
        ("notepad", "###"),
    ])
    def test_empty_or_symbol_only_inputs_score_zero(self, target: str, label: str) -> None:
        """Empty or symbol-only inputs cleanly return 0.0 without exception."""
        assert PrecisionAppMatcher.score_match(label, target) == 0.0

    @pytest.mark.parametrize("target", [
        r".*",
        r"(.*)+",
        r"a{1000}",
        r"[a-z]+",
        r"(?i)notepad",
        r"^notepad$",
        r"\bnotepad\b",
        r"$^",
        r"calc?",
        r"$100",
        r"c++",
    ])
    def test_regex_injection_strings_do_not_crash_or_redos(self, target: str) -> None:
        """Special regex characters in target are properly escaped and do not crash or ReDoS."""
        t0 = time.perf_counter()
        score = PrecisionAppMatcher.score_match("Normal Desktop Application Label", target)
        dt_ms = (time.perf_counter() - t0) * 1000.0

        assert score == 0.0
        assert dt_ms < 50.0, f"ReDoS suspected: execution took {dt_ms:.2f} ms"

    def test_unicode_and_emojis(self) -> None:
        """Handles accented characters, em-dashes, and emojis gracefully."""
        # Accented characters
        score_accent = PrecisionAppMatcher.score_match("Éditeur de texte", "éditeur")
        assert score_accent == 0.95

        # Em-dash separator
        score_emdash = PrecisionAppMatcher.score_match("Notepad — Notes", "notepad")
        assert score_emdash == 0.95

        # Cyrillic exact
        score_cyrillic = PrecisionAppMatcher.score_match("Блокнот", "блокнот")
        assert score_cyrillic == 1.0

        # CJK vs Latin
        score_cjk = PrecisionAppMatcher.score_match("记事本", "notepad")
        assert score_cjk == 0.0

        # Leading emoji
        score_emoji = PrecisionAppMatcher.score_match("📝 Notepad", "notepad")
        assert score_emoji >= 0.80


# ===========================================================================
# 5. UIElement Role Filtering & Thresholding
# ===========================================================================

class TestFindBestElementAdversarial:
    """
    Stress-tests candidate filtering, role validation, and high-volume performance.
    """

    def test_role_filtering(self) -> None:
        """Only elements with roles in PREFERRED_ROLES are eligible for matching."""
        valid_roles = ["Button", "ListItem", "MenuItem", "Hyperlink", "Image", "Pane", "Icon", "TreeItem", "TabItem", "Window"]
        invalid_roles = ["ScrollBar", "Separator", "Thumb", "ToolTip", "Header", "ProgressBar", "StatusBar", "Group", "Slider"]

        # Valid roles match
        for idx, role in enumerate(valid_roles, start=1):
            elem = UIElement.from_bbox(idx, (10, 10, 50, 50), label="Notepad", role=role)
            best = PrecisionAppMatcher.find_best_element("notepad", [elem], threshold=0.80)
            assert best is not None, f"Expected role '{role}' to be eligible"

        # Invalid roles are ignored
        for idx, role in enumerate(invalid_roles, start=100):
            elem = UIElement.from_bbox(idx, (10, 10, 50, 50), label="Notepad", role=role)
            best = PrecisionAppMatcher.find_best_element("notepad", [elem], threshold=0.80)
            assert best is None, f"Expected role '{role}' to be ignored"

    def test_candidate_ranking_and_threshold_rejection(self) -> None:
        """Best scoring element is chosen, and negative verbs/sub-threshold elements are excluded."""
        elements = [
            UIElement.from_bbox(1, (10, 10, 50, 50), label="Exit Notepad", role="Button"),
            UIElement.from_bbox(2, (10, 70, 50, 50), label="SmartScreen", role="Button"),
            UIElement.from_bbox(3, (10, 130, 50, 50), label="Open Notepad", role="Button"),
            UIElement.from_bbox(4, (10, 190, 50, 50), label="Notepad - Notes", role="Button"),
            UIElement.from_bbox(5, (10, 250, 50, 50), label="Notepad", role="Button"),
        ]

        # Candidate 5 is exact match (1.0), beating 4 (0.95) and 3 (0.85)
        best = PrecisionAppMatcher.find_best_element("notepad", elements, threshold=0.80)
        assert best is not None
        elem, score = best
        assert elem.id == 5
        assert score == 1.0

        # Remove candidate 5: Candidate 4 (0.95) should win
        best2 = PrecisionAppMatcher.find_best_element("notepad", elements[:4], threshold=0.80)
        assert best2 is not None
        elem2, score2 = best2
        assert elem2.id == 4
        assert score2 == 0.95

        # Only negative verb and collision elements remain: must return None
        best3 = PrecisionAppMatcher.find_best_element("notepad", elements[:2], threshold=0.80)
        assert best3 is None

    def test_high_volume_candidate_selection_perf(self) -> None:
        """Scans 5,000 UI elements in < 150ms without degradation."""
        elements = [
            UIElement.from_bbox(i + 1, ((i % 500) * 2, (i // 500) * 30, 50, 25), label=f"Catalog Item {i}", role="ListItem")
            for i in range(5000)
        ]
        target_elem = UIElement.from_bbox(99999, (100, 100, 80, 40), label="Notepad - Document 1", role="Button")
        elements.append(target_elem)

        t0 = time.perf_counter()
        best = PrecisionAppMatcher.find_best_element("notepad", elements, threshold=0.80)
        dt_ms = (time.perf_counter() - t0) * 1000.0

        assert best is not None
        assert best[0].id == 99999
        assert dt_ms < 150.0, f"Performance bottleneck: scanning 5000 elements took {dt_ms:.2f} ms"


# ===========================================================================
# 6. UniversalAppResolver 3-Tier State Machine Stress Testing
# ===========================================================================

class TestUniversalAppResolverAdversarial:
    """
    Adversarial verification of UniversalAppResolver state machine, loop-prevention, and preemption.
    """

    def test_empty_target_returns_wait(self) -> None:
        """Empty or blank target returns WAIT and does not advance launch counters."""
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        for empty_str in ["", "   ", "\t\n"]:
            plan = resolver.resolve_launch_action(empty_str, [])
            assert plan.action == ActionType.WAIT
            assert resolver._start_search_attempts == 0
            assert resolver._run_dialog_attempts == 0

    def test_state_machine_idempotence_at_exhaustion(self) -> None:
        """
        After both Tier 2 and Tier 3 have executed, repeated calls must remain in
        ActionType.WAIT and NEVER loop back to triggering Win or Win+R.
        """
        resolver = UniversalAppResolver(cadence_buffer_ms=0)
        target = "non_existent_app"

        # Tier 2 - Step A: Win key
        p1 = resolver.resolve_launch_action(target, [])
        assert p1.action == ActionType.HOTKEY and p1.keys == ["win"]

        # Tier 2 - Step B: Type target
        p2 = resolver.resolve_launch_action(target, [])
        assert p2.action == ActionType.TYPE and p2.text == f"{target}\n"

        # Tier 3 - Step A: Win+R chord
        p3 = resolver.resolve_launch_action(target, [])
        assert p3.action == ActionType.HOTKEY and p3.keys == ["win", "r"]

        # Tier 3 - Step B: Type target
        p4 = resolver.resolve_launch_action(target, [])
        assert p4.action == ActionType.TYPE and p4.text == f"{target}\n"

        # Exhaustion reached
        p5 = resolver.resolve_launch_action(target, [])
        assert p5.action == ActionType.WAIT
        assert "exhausted" in (p5.reasoning or "").lower()

        # Stress repeated calls at exhaustion (simulate cognitive pipeline polling)
        for i in range(20):
            p_loop = resolver.resolve_launch_action(target, [])
            assert p_loop.action == ActionType.WAIT, f"Iteration {i} broke idempotence with action {p_loop.action}"
            assert resolver._start_search_attempts == 1
            assert resolver._run_dialog_attempts == 1

    def test_target_app_switch_resets_counters_immediately(self) -> None:
        """Switching target app immediately resets state counters and triggers Tier 2 for new app."""
        resolver = UniversalAppResolver(cadence_buffer_ms=0)

        # Advance app1 to Tier 3
        resolver.resolve_launch_action("app1", [])
        resolver.resolve_launch_action("app1", [])
        resolver.resolve_launch_action("app1", [])
        assert resolver._start_search_attempts == 1
        assert resolver._run_opened is True

        # Now launch app2
        p_new = resolver.resolve_launch_action("app2", [])
        assert p_new.action == ActionType.HOTKEY
        assert p_new.keys == ["win"]
        assert resolver._start_search_attempts == 0
        assert resolver._run_dialog_attempts == 0
        assert resolver._search_opened is True
        assert resolver._run_opened is False

    def test_cancellation_preemption_latency(self) -> None:
        """Cancellation token set by hardware touch preemption breaks sleep in <20ms."""
        token = threading.Event()
        token.set()  # Hardware touch simulated

        resolver = UniversalAppResolver(cadence_buffer_ms=2000.0)
        resolver._search_opened = True

        t0 = time.perf_counter()
        plan = resolver.resolve_launch_action("notepad", [], cancellation_token=token)
        dt_ms = (time.perf_counter() - t0) * 1000.0

        assert plan.action == ActionType.TYPE
        assert dt_ms < 20.0, f"Touch preemption exceeded 20ms: took {dt_ms:.2f} ms"
