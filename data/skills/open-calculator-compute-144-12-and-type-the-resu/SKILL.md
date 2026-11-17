---
schema_version: 1
id: open-calculator-compute-144-12-and-type-the-resu
name: Calculator
version: 1
type: workflow
draft: false
state: ACTIVE
provenance: farmed
description: The user wants to open Calculator, compute 144 / 12, and type the result
  into the open Notepad window. We can launch the native Windows Calculator using
  the Run dialog (Win+R) to compute the expressio
trigger:
  goal_patterns: []
  keywords:
  - open
  - calculator
  - compute
  - '144'
  - type
  - result
  process_names:
  - CalculatorApp.exe
  min_score: 0.6
parameters: []
preconditions:
  container_process: CalculatorApp.exe
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
    text: calc
    keys:
    - enter
    submit: true
    clear_first: false
    wait_ms: 0
    success_criteria: The Calculator application window opens.
  - intent: INPUT_DATA
    verb: TYPE
    target_description: Calculator application
    text: 144/12=
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: The result '12' is displayed in Calculator.
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
    success_criteria: Notepad window is active and in focus.
  - intent: INPUT_DATA
    verb: TYPE
    target_description: Notepad text editing area
    text: '12'
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: The number '12' is typed into Notepad.
postconditions:
  success_criteria: The number '12' is typed into Notepad.
  expected_process: CalculatorApp.exe
invalidation:
  ttl_days: 30
  phash_max_hamming: 10
  max_consecutive_failures: 2
  visual_anchors:
  - phash: 80af55c06af507fa
    window_size:
    - 413
    - 213
    captured_at: '2026-11-16T08:35:33.082732Z'
  - phash: 80ae15d16af507fa
    window_size:
    - 413
    - 213
    captured_at: '2026-11-17T05:01:39.821853Z'
stats:
  created_at: '2026-11-15T23:44:14.195800Z'
  last_verified_at: '2026-11-17T05:02:02.902746Z'
  last_used_at: '2026-11-17T05:02:02.902746Z'
  success_count: 2
  failure_count: 0
  consecutive_failures: 0
---
