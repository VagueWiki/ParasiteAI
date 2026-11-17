---
schema_version: 1
id: close-notepad
name: notepad.exe
version: 1
type: workflow
draft: true
state: CANDIDATE
provenance: farmed
description: The user wants to close Notepad. Comparing options like taskkill or clicking
  the window close button versus using the standard Alt+F4 hotkey, Alt+F4 is the cleanest,
  most direct, and reliable native m
trigger:
  goal_patterns: []
  keywords:
  - close
  - notepad
  process_names: []
  min_score: 0.6
parameters: []
preconditions:
  container_process: null
  container_title_regex: null
  requires_launch: false
  launch_query: null
  launch_method: start_search
actions:
  steps:
  - intent: LAUNCH_OR_ACTIVATE
    verb: CLICK
    target_description: Notepad Window
    text: ''
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Notepad is active in the foreground.
  - intent: CONCLUDE
    verb: HOTKEY
    target_description: Notepad Close Window
    text: null
    keys:
    - alt
    - f4
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Notepad window is closed and terminated.
postconditions:
  success_criteria: Notepad window is closed and terminated.
  expected_process: null
invalidation:
  ttl_days: 30
  phash_max_hamming: 10
  max_consecutive_failures: 2
  visual_anchors: []
stats:
  created_at: '2026-11-15T23:39:43.042166Z'
  last_verified_at: '2026-11-15T23:39:43.042166Z'
  last_used_at: null
  success_count: 0
  failure_count: 0
  consecutive_failures: 0
---
