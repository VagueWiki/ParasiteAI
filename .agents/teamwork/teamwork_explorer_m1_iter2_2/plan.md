# Fix Plan: Robust Balanced-Brace / Depth-Counting Action JSON Extraction

## Target
- **File**: `parasite_ai/mind/brain_manager.py`
- **Location**: Lines 946–990 (`LocalBrainManager._extract_action_json`)
- **Failing Test**: `tests/test_stress_m1.py::TestHostileActionExtraction::test_preamble_with_multiple_braces_and_nested_json`

---

## Root Cause Analysis
The current implementation of `_extract_action_json` in `parasite_ai/mind/brain_manager.py:946-990` uses 4 passes:
1. `json.loads(raw_response.strip())`: Fails when conversational preamble or commentary exists.
2. `re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", ...)`: Fails when:
   - There are no markdown code fences around the JSON;
   - Fences use more than 3 backticks (e.g. ````json` or ````markdown`);
   - The JSON inside the fence contains nested objects, because the non-greedy regex `\{[\s\S]*?\}` truncates at the first inner `}`.
3. `re.search(r"\{[\s\S]*\}", ...)`: Greedy regex matches from the first `{` in the preamble (e.g. `Thought: {state: active}`) all the way to the last `}`, creating an invalid composite string that fails `json.loads`.
4. `re.findall(r"\{[\s\S]*?\}", ...)`: Non-greedy regex fails on ANY nested object (e.g. `{"metadata": {"depth": 2}}`) because it matches from `{` to the nearest `}`, truncating the object and producing malformed JSON syntax.

Because Python's standard `re` module cannot count recursive bracket depth, regular expressions cannot reliably extract nested JSON.

---

## Proposed Solution Architecture
Replace the regex-based passes with a 4-tier robust depth-counting and JSON decoding pipeline:

1. **Pass 1 (Direct JSON Parse)**:
   Fast-path `json.loads(raw_response.strip())` for clean responses.
2. **Pass 2 (Multi-Fence Extraction)**:
   Extract all markdown code fences using `re.compile(r"(`{3,})(?:json|markdown)?\s*\n?([\s\S]*?)\1", re.IGNORECASE)`. This matches 3, 4, or more backticks. Inside each fence, attempt direct parse, then balanced-brace depth extraction.
3. **Pass 3 (Balanced-Brace Depth Counting)**:
   A dedicated `@staticmethod _extract_balanced_json(text: str)` that scans `text` character by character tracking:
   - `in_string`: tracks whether current position is inside a `"..."` string literal.
   - `escape`: tracks backslash escapes `\` so escaped quotes `\"` or backslashes `\\` are correctly handled.
   - `depth`: integer counter incremented on `{` and decremented on `}` outside strings.
   - When `depth == 0` is reached, candidate slice `text[start : j + 1]` is tested via `json.loads`. If valid and contains `"action"`, it is returned immediately.
4. **Pass 4 (Resilient `JSONDecoder.raw_decode` Scan)**:
   Fallback scan iterating over every `{` in `raw_response` using `json.JSONDecoder().raw_decode`. Standard library C-accelerated decoder handles complex unicode, escapes, and recovers valid JSON even if preceded by unclosed or malformed braces in the preamble.

---

## Concrete Implementation for Worker

### Replacement in `parasite_ai/mind/brain_manager.py` (Lines 946–990)

```python
    @staticmethod
    def _extract_balanced_json(text: str) -> Optional[Dict[str, Any]]:
        """
        Extract first valid action JSON dictionary using balanced-brace depth counting.
        Properly handles quotes and backslash escape sequences so that braces within
        strings do not distort depth counting.
        """
        n = len(text)
        i = 0
        while i < n:
            if text[i] == '{':
                depth = 0
                in_string = False
                escape = False
                start = i
                for j in range(i, n):
                    char = text[j]
                    if in_string:
                        if escape:
                            escape = False
                        elif char == '\\':
                            escape = True
                        elif char == '"':
                            in_string = False
                    else:
                        if char == '"':
                            in_string = True
                        elif char == '{':
                            depth += 1
                        elif char == '}':
                            depth -= 1
                            if depth == 0:
                                candidate = text[start : j + 1]
                                try:
                                    parsed = json.loads(candidate.strip())
                                    if isinstance(parsed, dict) and "action" in parsed:
                                        return parsed
                                except Exception:
                                    pass
                                i = j
                                break
            i += 1
        return None

    @staticmethod
    def _extract_action_json(raw_response: str) -> Optional[Dict[str, Any]]:
        """
        Resilient multi-pass JSON extractor.
        Handles direct JSON, markdown code fences (```json ... ```),
        conversational preambles containing braces, nested dictionaries,
        and multiple sequential blocks.
        """
        if not raw_response or not isinstance(raw_response, str):
            return None

        # Pass 1: Direct JSON parsing
        try:
            parsed = json.loads(raw_response.strip())
            if isinstance(parsed, dict) and "action" in parsed:
                return parsed
        except Exception:
            pass

        # Pass 2: Markdown code fence extraction (supports 3+ backticks: ```, ````, etc.)
        fence_pattern = re.compile(r"(`{3,})(?:json|markdown)?\s*\n?([\s\S]*?)\1", re.IGNORECASE)
        for match in fence_pattern.finditer(raw_response):
            fence_content = match.group(2).strip()
            # Direct parse within fence
            try:
                parsed = json.loads(fence_content)
                if isinstance(parsed, dict) and "action" in parsed:
                    return parsed
            except Exception:
                pass
            # Balanced-brace scan within fence
            result = LocalBrainManager._extract_balanced_json(fence_content)
            if result:
                return result

        # Pass 3: Balanced-brace depth counting across full text
        result = LocalBrainManager._extract_balanced_json(raw_response)
        if result:
            return result

        # Pass 4: Resilient raw_decode scan from every '{'
        decoder = json.JSONDecoder()
        pos = 0
        n = len(raw_response)
        while pos < n:
            brace_idx = raw_response.find('{', pos)
            if brace_idx == -1:
                break
            try:
                obj, end_idx = decoder.raw_decode(raw_response, brace_idx)
                if isinstance(obj, dict) and "action" in obj:
                    return obj
                pos = max(brace_idx + 1, end_idx)
            except json.JSONDecodeError:
                pos = brace_idx + 1

        return None
```

---

## Worker Action Steps
1. Open `parasite_ai/mind/brain_manager.py`.
2. Locate `LocalBrainManager._extract_action_json` (around line 946).
3. Replace `_extract_action_json` with the updated methods `_extract_balanced_json` and `_extract_action_json` above.
4. Run verification tests:
   ```powershell
   .venv\Scripts\pytest.exe tests/test_stress_m1.py::TestHostileActionExtraction -v
   .venv\Scripts\pytest.exe tests/test_brain_manager.py -v
   ```
5. Confirm 100% pass on all `TestHostileActionExtraction` tests (11 of 11 passing, especially `test_preamble_with_multiple_braces_and_nested_json`).
