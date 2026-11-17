---
schema_version: 1
id: template-workflow-example
name: Template Semantic Workflow Skill
version: 1
type: workflow
draft: true
state: CANDIDATE
provenance: authored
description: <one paragraph summarizing what this workflow playbook accomplishes>
trigger:
  goal_patterns:
    - "^(?P<target_input>.+)$"
  keywords:
    - "<keyword>"
  process_names:
    - "<process_exe>"
  min_score: 0.6
parameters:
  - name: target_input
    description: <parameter description>
    required: true
preconditions:
  container_process: <process_exe>
  requires_launch: true
actions:
  steps:
    - intent: LAUNCH_OR_ACTIVATE
      verb: HOTKEY
      target_description: <semantic target or shortcut description>
      keys:
        - "<key>"
        - "<key>"
      success_criteria: <verifiable screen condition>
    - intent: INPUT_DATA
      verb: TYPE
      target_description: <semantic input field description>
      text: "{{target_input}}"
      success_criteria: <verifiable input completion condition>
postconditions:
  success_criteria: <goal-level verifiable condition>
  expected_process: <process_exe>
invalidation:
  ttl_days: 30
  phash_max_hamming: 10
  max_consecutive_failures: 2
  visual_anchors: []
---
# <Skill Name>

## Intent
<Explain what this skill achieves semantically without hardcoded coordinates.>

## Procedure
1. <Activate or focus target container window.>
2. <Execute semantic steps grounded by local vision.>

## Recovery Notes
<Describe how to recover if an action yields zero visual diff or a modal dialog appears.>
