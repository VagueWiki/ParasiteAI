---
schema_version: 1
id: calculator-evaluate
name: Calculator Keyboard Evaluate
version: 1
type: workflow
draft: false
state: ACTIVE
provenance: authored
description: Launch Calculator and evaluate a math expression via keyboard
trigger:
  goal_patterns:
  - ^(?:(?:open|launch|start)\s+calculator\s+(?:and\s+)?)?(?:calculate|compute|evaluate)\s+(?P<expression>[0-9+\-*/().
    ]+)$
  keywords:
  - calculate
  - calculator
  - compute
  process_names:
  - CalculatorApp.exe
  min_score: 0.6
parameters:
- name: expression
  description: Arithmetic expression to evaluate
  required: true
preconditions:
  container_process: CalculatorApp.exe
  container_title_regex: null
  requires_launch: true
  launch_query: calc
  launch_method: win_r
actions:
  steps:
  - intent: NAVIGATE
    verb: HOTKEY
    target_description: Calculator clear
    text: null
    keys:
    - escape
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Calculator display cleared to 0
  - intent: INPUT_DATA
    verb: TYPE
    target_description: Calculator expression input
    text: '{{expression}}'
    keys: null
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Expression entered into Calculator
  - intent: NAVIGATE
    verb: HOTKEY
    target_description: Calculator equals
    text: null
    keys:
    - enter
    submit: false
    clear_first: false
    wait_ms: 0
    success_criteria: Evaluated result displayed in Calculator
postconditions:
  success_criteria: Calculator displays the evaluated result
  expected_process: CalculatorApp.exe
invalidation:
  ttl_days: 30
  phash_max_hamming: 8
  max_consecutive_failures: 2
  visual_anchors:
  - phash: 94af41c11ef123fa
    window_size:
    - 413
    - 213
    captured_at: '2026-11-15T10:38:44.584272Z'
  - phash: b48d63991e70673a
    window_size:
    - 413
    - 213
    captured_at: '2026-11-15T17:58:23.178183Z'
  - phash: 908543d11ff123fe
    window_size:
    - 413
    - 213
    captured_at: '2026-11-15T23:39:56.401330Z'
stats:
  created_at: '2026-11-14T10:09:52.759640Z'
  last_verified_at: '2026-11-17T05:00:30.297406Z'
  last_used_at: '2026-11-17T05:00:30.297406Z'
  success_count: 11
  failure_count: 0
  consecutive_failures: 0
---
# Calculator Keyboard Evaluate

## Intent
Evaluate an arithmetic expression in Windows Calculator using keyboard input only (coordinate-free).

## Procedure
1. Launch `CalculatorApp.exe` if not already active.
2. Press `Escape` to clear any prior calculation.
3. Type `{{expression}}` and press `Enter`.
