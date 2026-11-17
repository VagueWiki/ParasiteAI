---
schema_version: 1
id: create-a-new-folder-named-reports-inside-c-paras
name: explorer.exe
version: 1
type: workflow
draft: false
state: ACTIVE
provenance: farmed
description: To create a folder inside C:\ParasiteAI\benchmarks\workspace, using native
  File Explorer is the most efficient and reliable native Windows approach. We can
  open the Run dialog, navigate directly to th
trigger:
  goal_patterns: []
  keywords:
  - create
  - new
  - folder
  - named
  - reports
  - inside
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
    target_description: Run dialog input
    text: null
    keys:
    - win
    - r
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Run dialog is visible on screen.
  - intent: NAVIGATE
    verb: TYPE
    target_description: Run dialog text input
    text: C:\ParasiteAI\benchmarks\workspace
    keys: null
    submit: true
    clear_first: false
    wait_ms: 0
    success_criteria: File Explorer window opens showing the workspace folder contents.
  - intent: INPUT_DATA
    verb: HOTKEY
    target_description: File Explorer workspace window
    text: null
    keys:
    - ctrl
    - shift
    - n
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: A new folder input field appears named 'New folder'.
  - intent: INPUT_DATA
    verb: TYPE
    target_description: New folder text input
    text: Reports
    keys: null
    submit: true
    clear_first: false
    wait_ms: 0
    success_criteria: The folder is renamed to 'Reports'.
  - intent: VERIFY_STATE
    verb: WAIT
    target_description: File Explorer window
    text: null
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Folder 'Reports' is displayed inside the workspace directory.
postconditions:
  success_criteria: Folder 'Reports' is displayed inside the workspace directory.
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
    captured_at: '2026-11-17T05:06:16.699625Z'
stats:
  created_at: '2026-11-16T08:39:58.573171Z'
  last_verified_at: '2026-11-17T05:06:30.820538Z'
  last_used_at: '2026-11-17T05:06:30.820538Z'
  success_count: 1
  failure_count: 0
  consecutive_failures: 0
---
