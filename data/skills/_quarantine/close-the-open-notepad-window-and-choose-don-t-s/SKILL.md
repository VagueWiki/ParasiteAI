---
schema_version: 1
id: close-the-open-notepad-window-and-choose-don-t-s
name: Notepad
version: 1
type: workflow
draft: false
state: INVALIDATED
provenance: farmed
description: To close the open Notepad window containing unsaved changes and choose
  'Don't Save', using the Alt+F4 hotkey to close Notepad followed by the 'Don't Save'
  hotkey (or navigation keys) is the most direc
trigger:
  goal_patterns: []
  keywords:
  - close
  - open
  - notepad
  - window
  - choose
  - don
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
  - intent: LAUNCH_OR_ACTIVATE
    verb: HOTKEY
    target_description: Notepad window
    text: ''
    keys:
    - alt
    - tab
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Notepad is the active foreground window.
  - intent: SELECT_OPTION
    verb: HOTKEY
    target_description: Notepad close button
    text: ''
    keys:
    - alt
    - f4
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: The save confirmation prompt appears.
  - intent: DISMISS_DIALOG
    verb: HOTKEY
    target_description: Don't Save button on confirmation dialog
    text: ''
    keys:
    - n
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: The Notepad window and prompt close entirely.
  - intent: CONCLUDE
    verb: WAIT
    target_description: Desktop view
    text: ''
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Notepad window is closed.
postconditions:
  success_criteria: Notepad window is closed.
  expected_process: notepad.exe
invalidation:
  ttl_days: 30
  phash_max_hamming: 10
  max_consecutive_failures: 2
  visual_anchors:
  - phash: d5850f810fa51fe5
    window_size:
    - 1287
    - 916
    captured_at: '2026-11-15T18:12:54.456223Z'
stats:
  created_at: '2026-11-15T10:54:25.078388Z'
  last_verified_at: '2026-11-15T18:13:04.232362Z'
  last_used_at: '2026-11-15T18:13:04.232362Z'
  success_count: 1
  failure_count: 0
  consecutive_failures: 0
---


<!-- Quarantined: Visual drift detected (min_hamming=14 > 10). -->
