---
schema_version: 1
id: open-notepad-type-saved-note-101-and-save-it-as
name: notepad.exe
version: 1
type: workflow
draft: false
state: ACTIVE
provenance: farmed
description: Notepad is the native Windows text editor best suited for quickly opening,
  typing, and saving plain text files like C:\ParasiteAI\benchmarks\workspace\note101.txt.
trigger:
  goal_patterns: []
  keywords:
  - open
  - notepad
  - type
  - saved
  - note
  - '101'
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
    verb: HOTKEY
    target_description: Windows Run dialog
    text: ''
    keys:
    - win
    - r
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Run dialog is open and focused
  - intent: INPUT_DATA
    verb: TYPE
    target_description: Run input field
    text: notepad
    keys:
    - enter
    submit: true
    clear_first: false
    wait_ms: 0
    success_criteria: Notepad window is active
  - intent: INPUT_DATA
    verb: TYPE
    target_description: Notepad text area
    text: Saved Note 101
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Text 'Saved Note 101' is visible in Notepad
  - intent: NAVIGATE
    verb: HOTKEY
    target_description: Notepad window
    text: ''
    keys:
    - ctrl
    - shift
    - s
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Save As dialog is open
  - intent: INPUT_DATA
    verb: TYPE
    target_description: File name input field
    text: C:\ParasiteAI\benchmarks\workspace\note101.txt
    keys:
    - enter
    submit: true
    clear_first: false
    wait_ms: 0
    success_criteria: Target file path is entered in the file name box
  - intent: CONCLUDE
    verb: WAIT
    target_description: Notepad window title
    text: ''
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Note101.txt is saved and displayed in Notepad title bar
postconditions:
  success_criteria: Note101.txt is saved and displayed in Notepad title bar
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
    captured_at: '2026-11-17T05:01:04.256268Z'
stats:
  created_at: '2026-11-16T08:35:08.420975Z'
  last_verified_at: '2026-11-17T05:01:13.017604Z'
  last_used_at: '2026-11-17T05:01:13.017604Z'
  success_count: 1
  failure_count: 0
  consecutive_failures: 0
---
