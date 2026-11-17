---
schema_version: 1
id: close-the-error-dialog-and-then-open-notepad
name: notepad.exe
version: 1
type: workflow
draft: false
state: INVALIDATED
provenance: farmed
description: The user wants to close the active 'Benchmark System Error' dialog and
  then open Notepad. Comparing options like clicking the dialog OK button versus using
  keyboard shortcuts, sending the Enter key is
trigger:
  goal_patterns: []
  keywords:
  - close
  - error
  - dialog
  - then
  - open
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
  - intent: DISMISS_DIALOG
    verb: HOTKEY
    target_description: Benchmark System Error Dialog OK Button
    text: null
    keys:
    - enter
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: The error dialog is closed and removed from the screen.
  - intent: LAUNCH_OR_ACTIVATE
    verb: HOTKEY
    target_description: Windows Run Dialog
    text: null
    keys:
    - win
    - r
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: The Run dialog is visible on screen.
  - intent: LAUNCH_OR_ACTIVATE
    verb: TYPE
    target_description: Run Dialog Open Field
    text: notepad
    keys:
    - enter
    submit: true
    clear_first: false
    wait_ms: 0
    success_criteria: Notepad application window opens and becomes active.
postconditions:
  success_criteria: Notepad application window opens and becomes active.
  expected_process: null
invalidation:
  ttl_days: 30
  phash_max_hamming: 10
  max_consecutive_failures: 2
  visual_anchors: []
stats:
  created_at: '2026-11-15T18:10:30.549143Z'
  last_verified_at: '2026-11-15T18:10:30.549143Z'
  last_used_at: '2026-11-16T08:42:28.034630Z'
  success_count: 0
  failure_count: 2
  consecutive_failures: 2
---


<!-- Quarantined: Exceeded max_consecutive_failures (2/2). -->
