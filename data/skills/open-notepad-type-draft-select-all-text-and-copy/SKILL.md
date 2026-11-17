---
schema_version: 1
id: open-notepad-type-draft-select-all-text-and-copy
name: Notepad
version: 1
type: workflow
draft: false
state: ACTIVE
provenance: farmed
description: To satisfy the user goal of opening Notepad, typing 'Draft', selecting
  all text, and copying it to the clipboard, native Windows Notepad is selected as
  the most reliable, lightweight tool.
trigger:
  goal_patterns: []
  keywords:
  - open
  - notepad
  - type
  - draft
  - select
  - copy
  process_names:
  - notepad.exe
  min_score: 0.6
parameters: []
preconditions:
  container_process: notepad.exe
  container_title_regex: null
  requires_launch: false
  launch_query: null
  launch_method: win_r
actions:
  steps:
  - intent: LAUNCH_OR_ACTIVATE
    verb: HOTKEY
    target_description: Windows Run dialog
    text: ''
    keys:
    - win
    - r
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: The Run dialog box is visible on the screen.
  - intent: INPUT_DATA
    verb: TYPE
    target_description: Run dialog input field
    text: notepad
    keys: null
    submit: true
    clear_first: false
    wait_ms: 0
    success_criteria: '''notepad'' is typed into the Run input box.'
  - intent: VERIFY_STATE
    verb: WAIT
    target_description: Notepad window
    text: ''
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Notepad is open with an empty text editing area.
  - intent: INPUT_DATA
    verb: TYPE
    target_description: Notepad text editor area
    text: Draft
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: '''Draft'' is visible in the Notepad window.'
  - intent: SELECT_OPTION
    verb: HOTKEY
    target_description: Notepad document content
    text: ''
    keys:
    - ctrl
    - a
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: All text in the document is highlighted.
  - intent: SELECT_OPTION
    verb: HOTKEY
    target_description: Notepad selected content
    text: ''
    keys:
    - ctrl
    - c
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: The text is copied to the system clipboard.
  - intent: CONCLUDE
    verb: WAIT
    target_description: Notepad application
    text: ''
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: The goal is fully achieved.
postconditions:
  success_criteria: The goal is fully achieved.
  expected_process: null
invalidation:
  ttl_days: 30
  phash_max_hamming: 10
  max_consecutive_failures: 2
  visual_anchors:
  - phash: 908543d11ff123fe
    window_size:
    - 413
    - 213
    captured_at: '2026-11-15T08:08:12.367467Z'
  - phash: 94af41c11ef123fa
    window_size:
    - 413
    - 213
    captured_at: '2026-11-15T10:39:13.017248Z'
  - phash: b48d61d98778257a
    window_size:
    - 413
    - 213
    captured_at: '2026-11-15T17:59:03.660713Z'
stats:
  created_at: '2026-11-15T01:42:58.281107Z'
  last_verified_at: '2026-11-17T05:00:57.931051Z'
  last_used_at: '2026-11-17T05:00:57.931051Z'
  success_count: 6
  failure_count: 0
  consecutive_failures: 0
---
