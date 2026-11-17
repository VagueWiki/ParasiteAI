---
schema_version: 1
id: minimize-notepad
name: Notepad
version: 1
type: workflow
draft: false
state: ACTIVE
provenance: farmed
description: To minimize the currently open Notepad window, using the native keyboard
  shortcut Win + Down Arrow is the most direct, reliable, and foolproof method without
  requiring visual coordinate targeting.
trigger:
  goal_patterns: []
  keywords:
  - minimize
  - notepad
  process_names:
  - notepad.exe
  min_score: 0.6
parameters: []
preconditions:
  container_process: notepad.exe
  container_title_regex: null
  requires_launch: false
  launch_query: null
  launch_method: start_search
actions:
  steps:
  - intent: SELECT_OPTION
    verb: HOTKEY
    target_description: Notepad window minimize command
    text: ''
    keys:
    - win
    - down
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Notepad is minimized to the taskbar.
  - intent: CONCLUDE
    verb: WAIT
    target_description: Desktop view
    text: ''
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Notepad window is no longer visible on screen.
postconditions:
  success_criteria: Notepad window is no longer visible on screen.
  expected_process: null
invalidation:
  ttl_days: 30
  phash_max_hamming: 10
  max_consecutive_failures: 2
  visual_anchors:
  - phash: e7185a3ce53ac338
    window_size:
    - 1920
    - 40
    captured_at: '2026-11-15T08:07:30.156689Z'
  - phash: dace2e4a2f442e72
    window_size:
    - 993
    - 519
    captured_at: '2026-11-17T05:00:13.633770Z'
stats:
  created_at: '2026-11-14T21:38:43.989364Z'
  last_verified_at: '2026-11-17T05:00:13.956195Z'
  last_used_at: '2026-11-17T05:00:13.956195Z'
  success_count: 2
  failure_count: 0
  consecutive_failures: 0
---
