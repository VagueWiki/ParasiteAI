---
schema_version: 1
id: open-c-parasiteai-benchmarks-workspace-seed-txt
name: Notepad
version: 1
type: workflow
draft: false
state: ACTIVE
provenance: farmed
description: The user wants to open 'C:\ParasiteAI\benchmarks\workspace\seed.txt'
  in Notepad and append ' - Approved' to the end. Using the Windows Run dialog (Win+R)
  is the most reliable, deterministic way to ope
trigger:
  goal_patterns: []
  keywords:
  - open
  - parasiteai
  - benchmarks
  - workspace
  - seed
  - txt
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
    target_description: Windows Run dialog
    text: ''
    keys:
    - win
    - r
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: The Run dialog box is open and focused.
  - intent: INPUT_DATA
    verb: TYPE
    target_description: Run dialog input text field
    text: notepad C:\ParasiteAI\benchmarks\workspace\seed.txt
    keys:
    - enter
    submit: true
    clear_first: false
    wait_ms: 0
    success_criteria: Notepad opens with seed.txt loaded.
  - intent: NAVIGATE
    verb: HOTKEY
    target_description: Notepad text editing area
    text: ''
    keys:
    - ctrl
    - end
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Cursor is positioned at the very end of the document text.
  - intent: INPUT_DATA
    verb: TYPE
    target_description: Notepad text editing area
    text: ' - Approved'
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: The text ' - Approved' is appended at the end of the file.
  - intent: CONCLUDE
    verb: HOTKEY
    target_description: Notepad save file shortcut
    text: ''
    keys:
    - ctrl
    - s
    submit: true
    clear_first: false
    wait_ms: 0
    success_criteria: File changes are saved successfully.
postconditions:
  success_criteria: File changes are saved successfully.
  expected_process: notepad.exe
invalidation:
  ttl_days: 30
  phash_max_hamming: 10
  max_consecutive_failures: 2
  visual_anchors:
  - phash: 908543d11ff123fe
    window_size:
    - 413
    - 213
    captured_at: '2026-11-16T08:35:13.983776Z'
stats:
  created_at: '2026-11-15T23:42:53.335422Z'
  last_verified_at: '2026-11-17T05:01:33.385604Z'
  last_used_at: '2026-11-17T05:01:33.385604Z'
  success_count: 2
  failure_count: 1
  consecutive_failures: 0
---
