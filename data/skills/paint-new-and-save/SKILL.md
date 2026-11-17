---
schema_version: 1
id: paint-new-and-save
name: Paint Launch and Save
version: 1
type: workflow
draft: false
state: ACTIVE
provenance: authored
description: Launch Microsoft Paint and save the canvas to a file path
trigger:
  goal_patterns:
  - ^open paint and save (?:as )?['"]?(?P<filename>.+?)['"]?$
  keywords:
  - paint
  - save
  process_names:
  - mspaint.exe
  min_score: 0.6
parameters:
- name: filename
  description: Target file path or filename to save
  required: true
preconditions:
  container_process: mspaint.exe
  container_title_regex: null
  requires_launch: true
  launch_query: mspaint
  launch_method: win_r
actions:
  steps:
  - intent: NAVIGATE
    verb: HOTKEY
    target_description: Paint Save dialog
    text: null
    keys:
    - f12
    wait_ms: 0
    success_criteria: Save As dialog opens in Paint
  - intent: INPUT_DATA
    verb: TYPE
    target_description: File name box
    text: '{{filename}}'
    keys: null
    wait_ms: 0
    success_criteria: Target filename entered in Save As dialog
  - intent: NAVIGATE
    verb: HOTKEY
    target_description: Confirm Save
    text: null
    keys:
    - enter
    wait_ms: 0
    success_criteria: Image saved to disk
postconditions:
  success_criteria: Paint saved the canvas to the target path
  expected_process: mspaint.exe
invalidation:
  ttl_days: 30
  phash_max_hamming: 8
  max_consecutive_failures: 2
  visual_anchors:
  - phash: c98535a535a534f5
    window_size:
    - 423
    - 480
    captured_at: '2026-11-14T17:28:11.173824Z'
stats:
  created_at: '2026-11-14T10:10:47.192162Z'
  last_verified_at: '2026-11-14T17:52:45.364953Z'
  last_used_at: '2026-11-14T17:52:45.364953Z'
  success_count: 3
  failure_count: 0
  consecutive_failures: 0
---
# Paint Launch and Save

## Intent
Launch Microsoft Paint and save the canvas to `{{filename}}` using keyboard shortcuts.

## Procedure
1. Launch `mspaint.exe` if not already active.
2. Press `F12` to open Save As.
3. Type `{{filename}}` and press `Enter`.
