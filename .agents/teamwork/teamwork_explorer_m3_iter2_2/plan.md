# Implementation Plan: Defect 2 (IEEE 754 Floating-Point Truncation in Telemetry Step Progress)

## 1. Defect Summary & Root Cause

### Location
`parasite_ai/ui/companion_dock.py` at line 589:
```python
587:        if total_steps > 0:
588:            self.step_label.setText(f"Step: {current_step}/{total_steps}")
589:            pct = int((current_step / total_steps) * 100)
590:            self.step_progress.setValue(min(100, max(0, pct)))
591:        else:
592:            self.step_label.setText("Step: Idle")
593:            self.step_progress.setValue(0)
```

### Root Cause
1. In IEEE 754 binary floating-point representation (double precision, 64-bit float), `29 / 100` evaluates to `0.289999999999999980015985593945...` because 0.29 cannot be represented exactly as a finite binary fraction.
2. Multiplying by 100 yields `28.9999999999999964472863211995...`.
3. Python's `int(...)` function truncates toward zero (discarding fractional digits). As a result:
   - `int((29 / 100) * 100)` evaluates to `28` instead of `29` (1% error).
   - `int((57 / 100) * 100)` evaluates to `56` instead of `57` (1% error).
   - `int((58 / 100) * 100)` evaluates to `57` instead of `58` (1% error).
4. This causes `tests/test_companion_dock_adversarial.py::TestCompanionDockAdversarial::test_telemetry_step_precision_calculation` to fail with:
   `AssertionError: Step progress truncation bug: expected 29% but got 28%`

---

## 2. Comparative Analysis of Fix Options

| Formula | Implementation | Step 29/100 | Step 57/100 | Step 58/100 | Step 23/40 (57.5%) | Step 2/3 (66.7%) | Edge Cases (c < 0, c > t, t <= 0) | Mismatches across 500k pairs (t <= 1000) |
|---|---|---|---|---|---|---|---|---|
| **A (Current Buggy)** | `pct = int((current_step / total_steps) * 100)` | 28 (FAIL) | 56 (FAIL) | 57 (FAIL) | 57 | 66 | Handled by guard & clamp | Many |
| **B (Challenger Suggestion)** | `pct = round((current_step / total_steps) * 100)` | 29 (PASS) | 57 (PASS) | 58 (PASS) | 57 (loses 0.5% precision: `(23/40)*100 = 57.49999999999999`) | 67 (PASS) | Handled by guard & clamp | 30 |
| **C (Integer Floor Division)** | `pct = (current_step * 100) // total_steps` | 29 (PASS) | 57 (PASS) | 58 (PASS) | 57 (truncates downward) | 66 (truncates downward) | Handled by guard & clamp | Underestimates progress |
| **D (Recommended Optimal)** | `pct = round((current_step * 100) / total_steps)` | 29 (PASS) | 57 (PASS) | 58 (PASS) | 58 (exact round-half-to-even) | 67 (PASS) | Handled by guard & clamp | **0 (Zero mismatches)** |

### Why Option D is Superior
- In `(current_step * 100) / total_steps`:
  - `current_step * 100` is computed in Python exact arbitrary-precision integer arithmetic, with **0 bits of precision lost**.
  - A single float division `... / total_steps` is performed immediately before `round()`.
  - For fractions whose decimal ends in `.5` (e.g. `23/40 = 57.5%`), `2300 / 40` evaluates to float `57.5` exactly (since powers of 2 in denominator have exact binary representations), correctly resolving to `58` under Python's round-half-to-even.
  - In an empirical scan of all 500,500 numerator/denominator combinations (`1 <= total_steps <= 1000`, `0 <= current_step <= total_steps`), Option D produced **0 mismatches** against exact rational arithmetic, whereas Option B had 30 precision degradation failures.

---

## 3. Edge Cases & Invariants

1. **Zero Total Steps (`total_steps == 0`)**:
   - Guarded by line 587 (`if total_steps > 0:`).
   - When `total_steps == 0`, execution falls through to `else:`, setting `step_label` to `"Step: Idle"` and `step_progress` to `0`.
   - Division by zero is completely prevented.
2. **Negative Total Steps (`total_steps < 0`)**:
   - `total_steps > 0` evaluates to `False`.
   - Execution falls through to `else:`, setting `step_label` to `"Step: Idle"` and `step_progress` to `0`.
   - Prevents negative division or progress inversion.
3. **Negative Current Step (`current_step < 0`, `total_steps > 0`)**:
   - Example: `current_step = -20, total_steps = 100`.
   - `step_label` displays `"Step: -20/100"`.
   - `pct = round((-20 * 100) / 100) = -20`.
   - `min(100, max(0, -20))` evaluates to `0`.
   - Progress bar is clamped to `0`.
4. **Current Step Overshoot (`current_step > total_steps`, `total_steps > 0`)**:
   - Example: `current_step = 500, total_steps = 100`.
   - `step_label` displays `"Step: 500/100"`.
   - `pct = round((500 * 100) / 100) = 500`.
   - `min(100, max(0, 500))` evaluates to `100`.
   - Progress bar is clamped to `100`.
5. **Exact Boundaries (`current_step == 0` or `current_step == total_steps`)**:
   - `current_step == 0` -> `pct = 0`, progress bar = `0`.
   - `current_step == total_steps` -> `pct = 100`, progress bar = `100`.
6. **Type Safety with PyQt6 QProgressBar**:
   - `QProgressBar.setValue(int)` requires a C++ `int`.
   - Python 3 `round(...)` returns an `int`.
   - Clamping `min(100, max(0, pct))` preserves the `int` type.

---

## 4. Coordination with Defect 3

In `CompanionDock.update_telemetry`:
```python
    @pyqtSlot(str)
    @pyqtSlot(str, int, int)
    def update_telemetry(self, text: str, current_step: int = 0, total_steps: int = 0) -> None:
```
While fixing the percentage calculation at line 589, the worker should ensure that `@pyqtSlot(str, int, int)` is added alongside `@pyqtSlot(str)` (or coordinated with Explorer 3's plan) so that multi-argument telemetry emissions from `UIBridge` can invoke `update_telemetry` across threads via `QueuedConnection` without dropping `current_step` or `total_steps`.

---

## 5. Precise Code Replacement for Worker

Target file: `parasite_ai/ui/companion_dock.py`
Target lines: 587-590

```python
<<<< ORIGINAL (lines 587-590)
        if total_steps > 0:
            self.step_label.setText(f"Step: {current_step}/{total_steps}")
            pct = int((current_step / total_steps) * 100)
            self.step_progress.setValue(min(100, max(0, pct)))
==== REPLACEMENT
        if total_steps > 0:
            self.step_label.setText(f"Step: {current_step}/{total_steps}")
            pct = round((current_step * 100) / total_steps)
            self.step_progress.setValue(min(100, max(0, pct)))
>>>>
```
