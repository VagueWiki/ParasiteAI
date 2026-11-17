---
schema_version: 1
id: open-notepad-notes
name: Notepad Note Flow
version: 1
type: workflow
draft: false
state: ACTIVE
provenance: authored
description: Write structured note in Notepad
trigger:
  goal_patterns:
  - ^write note (?P<note>.+)$
  keywords:
  - write
  - note
  process_names:
  - notepad.exe
  min_score: 0.6
parameters:
- name: note
  description: Text body
  required: true
preconditions:
  container_process: notepad.exe
  container_title_regex: null
  requires_launch: false
  launch_query: null
  launch_method: start_search
actions:
  steps:
  - intent: INPUT_DATA
    verb: TYPE
    target_description: null
    text: '{{note}}'
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Text appears inside Notepad
postconditions:
  success_criteria: Note typed
  expected_process: notepad.exe
invalidation:
  ttl_days: 30
  phash_max_hamming: 8
  max_consecutive_failures: 2
  visual_anchors: []
stats:
  created_at: '2026-11-17T18:45:25.675002Z'
  last_verified_at: '2026-11-17T18:45:25.675002Z'
  last_used_at: null
  success_count: 0
  failure_count: 0
  consecutive_failures: 0
---
