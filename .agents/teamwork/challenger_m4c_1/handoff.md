# Handoff Report: Challenger M4C 1 (Dual-Channel Output Router Stress Verification)

**Verdict**: `REQUEST_CHANGES`

---

## 1. Observation

### Empirical Test Execution
- Executed `tests/test_challenger_m4c_stress.py` via PowerShell:
  `.\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4c_stress.py -v`
- **Result**: 27 PASSED, 10 FAILED in 1.40s.

### Verbatim Failures Observed

1. **Decimal & Signed Coordinate Regex Bypass in `_sanitize_text`**:
   - `test_sanitize_text_strips_all_coordinate_and_dimension_variants[Target at ( -100 , +250.5 ) coordinates]`
     `AssertionError: Leaked coordinate in sanitized: 'Target at ( -100 , +250.5 ) coordinates'`
   - `test_sanitize_text_strips_all_coordinate_and_dimension_variants[Target at (+100, +250) coordinates]`
     `AssertionError: Leaked coordinate in sanitized: 'Target at (+100, +250) coordinates'`
   - `test_sanitize_text_strips_all_coordinate_and_dimension_variants[Target at ( 100.5 , 200.25 ) coordinates]`
     `AssertionError: Leaked coordinate in sanitized: 'Target at ( 100.5 , 200.25 ) coordinates'`
   - `test_sanitize_text_strips_all_coordinate_and_dimension_variants[Multiple (10, 20) and (-30.5, 40.5) on 800x600 screen]`
     `AssertionError: Leaked coordinate in sanitized: 'Multiple and (-30.5, 40.5) on screen'`

2. **Coordinate Leaks into Persona Monologue and UI Speech**:
   - `test_speech_with_decimal_coordinate_in_rationale`
     `AssertionError: Channel B speech leaked coordinate tuple '( -100 , +250.5 )': 'Click the target at ( -100 , +250.5 ) to resolve focus.'`
   - `test_speech_with_decimal_coordinate_in_step_description`
     `AssertionError: Channel B speech leaked coordinate tuple '( -100 , +250.5 )': "Gemini suggested we try click submit button at ( -100 , +250.5 ) on display. Let's give that a shot!"`
   - `test_bridge_never_receives_forbidden_tokens_on_hostile_input`
     `AssertionError: Channel B speech leaked coordinate tuple '( -50 , 100.5 )': "Gemini suggested we try press button at ( -50 , 100.5 ) on. Let's give that a shot!"`
   - `test_pipeline_step_with_adversarial_coordinates_in_blueprint`
     `AssertionError: Channel B speech leaked coordinate tuple '( -100 , +250.5 )': "Gemini suggested we try click button at ( -100 , +250.5 ) on display. Let's give that a shot!"`

3. **Error Token Suppression Gaps**:
   - `test_http_429_in_rationale_string`
     Input payload: `{"rationale": "Encountered HTTP 429: Resource exhausted from backend service", "steps": []}`
     Output speech: `'Encountered HTTP 429: Resource exhausted from backend service'`
     `AssertionError: Channel B speech leaked error token '429'`
   - `test_quota_exceeded_and_503_in_rationale_string`
     Input payload: `{"rationale": "Quota exceeded. 503 Service Unavailable.", "steps": []}`
     Output speech: `'Quota exceeded. 503 Service Unavailable.'`
     `AssertionError: Channel B speech leaked error token 'quota exceeded'`

### Code Inspection Observations
In `parasite_ai/mind/dual_mind.py`:
- Line 870:
  ```python
  text = re.sub(r"\(\s*-?\d+\s*,\s*-?\d+\s*\)", "", text)
  ```
  The coordinate regex `-?\d+` only matches signed integers; it does not match positive signs (`+`) or decimal points (`.` or `\.`).
- Lines 816-833:
  ```python
  error_tokens = (
      "error:",
      "exception",
      "resource_exhausted",
      "code 429",
      "rate limit",
      "traceback",
      "stack trace",
      "status_code",
      "failed with",
      "syntaxerror",
      "typeerror",
      "valueerror",
  )
  is_error = any(kw in clean_text.lower() for kw in error_tokens) or bool(
      re.search(r"\berror\b\s*:", clean_text, re.IGNORECASE)
  )
  ```
  `error_tokens` requires `"code 429"` (misses `"HTTP 429"` and standalone `"429"`) and `"resource_exhausted"` with an underscore (misses `"Resource exhausted"` with spaces), as well as `"quota exceeded"`, `"503 service"`, and `"500 internal"`.

---

## 2. Logic Chain

1. **Step 1**: The Milestone 4C invariant contract explicitly requires:
   "Channel B persona monologue contains ZERO raw JSON syntax, ZERO backticks, ZERO markdown code blocks, ZERO coordinates, and ZERO unhandled error codes. UIBridge.notify_speech() is never called with forbidden tokens."
2. **Step 2**: In `DualChannelRouter._sanitize_text()` (line 870), the regular expression `\(\s*-?\d+\s*,\s*-?\d+\s*\)` only strips integer coordinate pairs.
3. **Step 3**: When an advisor returns decimal coordinates (e.g. `( -100 , +250.5 )`, `( 100.5 , 200.25 )`), positive signs (e.g. `(+100, +250)`), or mixed floating-point offsets, the regex produces no match and leaves the coordinate string completely intact.
4. **Step 4**: When `translate_to_persona_voice()` processes either a step description containing coordinates or a rationale containing coordinates, the unsanitized coordinate string is interpolated into speech.
5. **Step 5**: `route_consultation_output()` invokes `self.bridge.notify_speech(persona_speech)` with the coordinate string intact, and `DualMindPipeline.step()` records and emits the unsanitized speech. This violates Invariant 3.
6. **Step 6**: In `translate_to_persona_voice()`, error token checking matches `"code 429"` instead of generic `429` / `HTTP 429`, and `"resource_exhausted"` instead of `"resource exhausted"`. When advisor responses contain standard Google Cloud / Gemini REST API error text (e.g., `Encountered HTTP 429: Resource exhausted from backend service`), `is_error` evaluates to `False`.
7. **Step 7**: Because `is_error` is `False` and `clean_text` is non-empty, the router returns the raw error string directly into persona voice and `UIBridge.notify_speech()`, violating Invariant 2.

---

## 3. Caveats

- Tests for deeply nested JSON (30+ levels), unclosed markdown fences, multi-tick fences, and 10,000-character payloads without catastrophic backtracking (ReDoS) **all passed cleanly**.
- Tests for prompt injection code block stripping (```python, ```bash, etc.) **passed cleanly**.
- The existing test suite `tests/test_dual_channel_output.py` (22 tests) passes 100% because it only tests integer coordinates `(450, 220)` and error payload `{"error": "RESOURCE_EXHAUSTED", "code": 429}`.

---

## 4. Conclusion & Actionable Fixes

**Verdict**: `REQUEST_CHANGES`

Two defects must be corrected in `parasite_ai/mind/dual_mind.py`:

### Action Item 1: Harden Coordinate Regular Expression in `_sanitize_text`
In `parasite_ai/mind/dual_mind.py`, line 870:
Replace:
```python
text = re.sub(r"\(\s*-?\d+\s*,\s*-?\d+\s*\)", "", text)
```
With:
```python
text = re.sub(r"\(\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)\s*,\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)\s*\)", "", text)
```
This strips integer, float, signed, and decimal coordinates with arbitrary whitespace.

### Action Item 2: Expand Error Token Detection in `translate_to_persona_voice`
In `parasite_ai/mind/dual_mind.py`, lines 816-833:
Expand `error_tokens` and error detection to:
```python
error_tokens = (
    "error:",
    "exception",
    "resource_exhausted",
    "resource exhausted",
    "code 429",
    "429",
    "rate limit",
    "quota exceeded",
    "503 service",
    "500 internal",
    "traceback",
    "stack trace",
    "status_code",
    "failed with",
    "syntaxerror",
    "typeerror",
    "valueerror",
)
is_error = (
    any(kw in clean_text.lower() for kw in error_tokens)
    or bool(re.search(r"\berror\b\s*:", clean_text, re.IGNORECASE))
    or bool(re.search(r"\b(?:429|500|502|503)\b", clean_text))
)
```

---

## 5. Verification Method

To verify the fixes independently:
1. Run the empirical stress suite:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_challenger_m4c_stress.py -v
   ```
   **Pass Condition**: All 37 tests PASS (0 failures).
2. Run the regression baseline suite:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/test_dual_channel_output.py -v
   ```
   **Pass Condition**: All 22 tests PASS (0 failures).
