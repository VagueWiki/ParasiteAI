# Handoff Report: Milestone M4 Challenger 1 (Hybrid Screen Grounding Adversarial Stress)

## 1. Observation

### Verification Executions and Empirical Evidence
- Executed: `uv run pytest tests/test_grounding.py tests/test_challenger_m4_1.py -v`
- Result: **41 passed in 5.20s** (13 baseline grounding tests + 28 new adversarial stress tests).
- All 28 adversarial tests in `tests/test_challenger_m4_1.py` passed with 0 failures, 0 warnings, and 0 memory or recursion errors.

### Direct Code Observations in Target Modules
1. **Spatial IoU & Containment Boundary Thresholds** (`parasite_ai/vision/grounding.py:59-102`, `110-111`):
   ```python
   IOU_THRESHOLD = 0.35
   CONTAINMENT_THRESHOLD = 0.70
   ```
   - In `compute_iou` (`grounding.py:77-80`):
     ```python
     if union <= 0:
         return 0.0
     return float(intersection / union)
     ```
     Zero-area, negative dimension, and disjoint boxes return `0.0` safely with no `ZeroDivisionError`.
   - In `compute_containment` (`grounding.py:97-101`):
     ```python
     inner_area = max(0, wa) * max(0, ha)
     if inner_area <= 0:
         return 0.0
     return float(intersection / inner_area)
     ```
     Degenerate inner boxes return `0.0` without dividing by zero.
   - Verified that boxes at IoU 0.342 remain distinct while boxes at IoU 0.351 merge properly.
   - Verified that boxes at containment 0.69 remain distinct while boxes at containment 0.71 merge properly.

2. **UIA Tree Depth and Element Blowout Safeguards** (`parasite_ai/vision/grounding.py:220-225`, `446`):
   ```python
   for control, depth in auto.WalkControl(root_control, includeTop=False, maxDepth=self._depth_limit):
       if len(raw_elements) >= 120:
           break
   ```
   - Tree walk correctly bounds recursion depth (`maxDepth=self._depth_limit = 5`).
   - Hard circuit breaker breaks loop when raw elements reach 120.
   - Tested against 20 levels of nesting, 600+ controls, and an infinite generator control stream; in all cases execution terminated safely and strictly adhered to `max_som_elements = 60`.

3. **RapidOCR Fallback Under Non-Standard Image Arrays** (`parasite_ai/vision/grounding.py:307-353`):
   - Input frames of shapes `(1, 1, 3)`, `(1080, 1920, 3)` (pure black, pure white), uint16, float32 with NaNs, `(100, 100, 4)` RGBA, and `(100, 100)` 2D grayscale were processed cleanly without throwing unhandled exceptions.
   - Malformed OCR bounding structures (empty items, single-element arrays, non-float confidences, corrupt polygon vertices) are safely caught and skipped by the defensive `try/except Exception as exc:` block at lines 355-395.

4. **Degenerate Set-of-Mark Tags & Hostile Inputs** (`parasite_ai/vision/grounding.py:257-270`, `435-467`, `470-484`):
   - Labels exceeding 80 characters are clamped via `str(name).strip()[:80]`.
   - Empty/whitespace labels fall back from Name -> HelpText -> non-auto AutomationId -> `""`, formatted as `(no label)` in `format_som_summary`.
   - Hostile prompt injection payloads (`{"action": "click"}`, HTML/script tags, quotes, newlines, emojis) are preserved accurately without crashing or corrupting Set-of-Mark summary format.
   - Interactive role filtering (`grounding.py:247-256`) correctly accepts standard roles, applies PaneControl size/name restrictions (`width <= 400 and height <= 150` with explicit name), and discards unregistered controls.

5. **Screen Capture and Frame Diff Invariants** (`parasite_ai/vision/capture.py:17-54`, `113-139`):
   - `compute_frame_diff` handles `None`, shape mismatches, 1x1 arrays, and sub-threshold noise (<= 15) returning accurate float ratios.
   - `capture_rect` handles zero/negative sizes and out-of-screen bounds returning fallback blank arrays without crashing.

---

## 2. Logic Chain

1. **Premise**: Hybrid screen grounding must operate reliably on real Windows desktops where UI Automation trees can be arbitrarily deep or malformed, applications can render non-standard canvas controls lacking UIA metadata, and image captures may encounter transient screen anomalies.
2. **Deduplication Correctness**: Empirical testing verified that IoU and containment metrics compute accurately across both positive and multi-monitor negative coordinate spaces. Threshold transitions at 0.35 IoU and 0.70 containment cleanly distinguish overlapping controls from distinct adjacent elements.
3. **Denial of Service Resistance**: Trees with 600+ elements or infinite streams are clamped by the 120-element walk limit and the 60-element Set-of-Mark limit, preventing unbounded memory consumption and excessive prompt bloat in cognitive passes.
4. **Resilience to Input Corruption**: Feeding 1x1, black, white, 16-bit, float32 with NaNs, RGBA, and malformed OCR returns revealed zero crashes or unhandled exceptions due to comprehensive guard checks.
5. **Set-of-Mark Representation**: Label resolution, formatting, and prompt generation handle missing labels, hostile JSON injections, and degenerate geometry cleanly.

---

## 3. Caveats

- **Hardware Display Topology**: Testing verified multi-monitor coordinates (negative x/y planes), but physical display resolution switches or DPI changes occurring mid-frame capture were simulated via mock rather than physical hardware monitor hotplugging.
- **External Failures**: A full-workspace test run (`uv run pytest`) showed 4 failures in `tests/test_challenger_m4_2.py`, which is owned by peer Challenger 2 (testing Browser Offloader / DualMind). Those failures are wholly outside the Hybrid Screen Grounding scope (`parasite_ai/vision/grounding.py` and `parasite_ai/vision/capture.py`), where 100% of tests pass.

---

## 4. Conclusion

**Verdict: `APPROVE`**

Feature 12 (Hybrid Screen Grounding: `parasite_ai/vision/grounding.py`, `parasite_ai/vision/capture.py`) is exceptionally robust. It cleanly handles extreme spatial IoU/containment boundary transitions, deep UIA tree blowout, non-standard image arrays, and degenerate Set-of-Mark tags without crashing, leaking memory, or corrupting prompt injection summaries.

---

## 5. Verification Method

To independently verify all findings:
```powershell
uv run pytest tests/test_grounding.py tests/test_challenger_m4_1.py -v
```

Expected output:
```
============================= 41 passed in 5.20s ==============================
```
