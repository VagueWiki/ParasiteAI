---
schema_version: 1
id: notepad-write-text
name: Notepad Launch and Write
version: 1
type: workflow
draft: false
state: ACTIVE
provenance: authored
description: Launch Notepad if needed and type text into the editor
trigger:
  goal_patterns:
  - ^(?:open|launch|start)\s+notepad\s+and\s+(?:write|type)\s+['"]?(?P<text>.+?)['"]?$
  - ^(?:write|type)\s+['"]?(?P<text>.+?)['"]?\s+(?:in|into)\s+notepad$
  keywords:
  - notepad
  - write
  - type
  process_names:
  - notepad.exe
  min_score: 0.6
parameters:
- name: text
  description: Text to type into Notepad
  required: true
preconditions:
  container_process: notepad.exe
  container_title_regex: null
  requires_launch: true
  launch_query: notepad
  launch_method: win_r
actions:
  steps:
  - intent: INPUT_DATA
    verb: TYPE
    target_description: Notepad editor
    text: '{{text}}'
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Typed text appears inside Notepad
postconditions:
  success_criteria: Notepad contains the requested text
  expected_process: notepad.exe
invalidation:
  ttl_days: 30
  phash_max_hamming: 8
  max_consecutive_failures: 2
  visual_anchors:
  - phash: e6391839c53bc738
    window_size:
    - 1920
    - 40
    captured_at: '2026-11-15T07:45:28.049817Z'
  - phash: 908543d11ff123fe
    window_size:
    - 413
    - 213
    captured_at: '2026-11-16T08:31:36.307107Z'
stats:
  created_at: '2026-11-14T18:17:20.272974Z'
  last_verified_at: '2026-11-17T04:58:56.368955Z'
  last_used_at: '2026-11-17T04:58:56.368955Z'
  success_count: 3
  failure_count: 1
  consecutive_failures: 0
---
# Notepad Launch and Write

## Intent
Open Windows Notepad via Win+R when not already active and type the requested text directly.
