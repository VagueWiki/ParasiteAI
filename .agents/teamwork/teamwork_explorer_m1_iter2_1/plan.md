# Implementation Plan for Worker — Milestone M1 Iteration 2

## Target File
`parasite_ai/mind/brain_manager.py`

---

## Executive Summary
Investigation identified 4 architectural defects in `parasite_ai/mind/brain_manager.py`:
1. **Re-entrant Join Crash**: `cancel_download()` crashes with `RuntimeError: cannot join current thread` when called from within `progress_callback` on the download thread, because `self._download_thread.join()` is called by the thread on itself.
2. **Inference State Restoration Race & Clobber**: `generate()` uses `finally: self.state = prev_state` without locking or counting concurrent requests. Concurrent calls capture `prev_state = INFERRING` and permanently freeze the manager in `INFERRING`. Furthermore, concurrent state mutations (`toggle_browser_only_mode`, `unload_model`) are clobbered when inference finishes.
3. **VRAM Headroom Budget Underflow**: `_instantiate_local_engine()` fails to check `free_mb < req_mb` or `free_mb < model_req_vram` when `gpu_layers == -1`, attempting full GPU offload on constrained VRAM and triggering CUDA OOM.
4. **JSON Extractor Preambles with Nested Objects**: `_extract_action_json()` fails on outputs containing preambles with `{...}` combined with nested JSON objects, because regex Pass 3 greedily spans from the first preamble `{` to the last `}`, while Pass 4 non-greedily truncates at the first closing `}` inside nested objects.

All 4 fixes have been verified empirically in memory against the full 111-test suite, achieving **111 passed in 9.60s (100% pass rate)**.

---

## Detailed Line-by-Line Changes for Worker

### Change 1: Initialize Inference Counter and Pre-Infer State
**File**: `parasite_ai/mind/brain_manager.py`  
**Location**: `LocalBrainManager.__init__` around lines 462–466

#### Before:
```python
        self._download_thread: Optional[threading.Thread] = None
        self._cancel_download_event = threading.Event()
        self._current_progress: Optional[DownloadProgress] = None
        self._lock = threading.RLock()

        # Initialize storage and assess initial status
```

#### After:
```python
        self._download_thread: Optional[threading.Thread] = None
        self._cancel_download_event = threading.Event()
        self._current_progress: Optional[DownloadProgress] = None
        self._lock = threading.RLock()
        self._inferring_count: int = 0
        self._pre_infer_state: Optional[BrainState] = None

        # Initialize storage and assess initial status
```

---

### Change 2: VRAM Headroom Guard in Engine Instantiation
**File**: `parasite_ai/mind/brain_manager.py`  
**Location**: `_instantiate_local_engine` around lines 513–530

#### Before:
```python
    def _instantiate_local_engine(self, model_path: Union[Path, str]) -> bool:
        """Try instantiating LlamaCppBackend, fallback to mock or endpoint."""
        used_mb, free_mb = check_vram_headroom()
        req_mb = self.config.brain.local_model.vram_budget_mb

        gpu_layers = self.config.brain.local_model.gpu_layers
        if free_mb < 2000:
            # Low VRAM: reduce layers to CPU fallback
            gpu_layers = 0

        try:
            backend = LlamaCppBackend(
```

#### After:
```python
    def _instantiate_local_engine(self, model_path: Union[Path, str]) -> bool:
        """Try instantiating LlamaCppBackend, fallback to mock or endpoint."""
        used_mb, free_mb = check_vram_headroom()
        req_mb = self.config.brain.local_model.vram_budget_mb

        path_obj = Path(model_path)
        matched = next((m for m in CURATED_MODELS if m["filename"] == path_obj.name), None)
        model_req_vram = matched["vram_required_mb"] if matched else req_mb

        gpu_layers = self.config.brain.local_model.gpu_layers
        if free_mb < 2000:
            # Low VRAM: reduce layers to CPU fallback
            gpu_layers = 0
        elif gpu_layers == -1 and (free_mb < req_mb or free_mb < model_req_vram):
            # Headroom guard: Free VRAM is below model requirement or budget, avoid CUDA OOM from full offload
            if matched and matched.get("recommended_gpu_layers", -1) != -1:
                gpu_layers = matched["recommended_gpu_layers"]
            else:
                gpu_layers = 16 if free_mb >= 2000 else 0

        try:
            backend = LlamaCppBackend(
```

---

### Change 3: Immediate Callback Cancellation Guard in `_download_worker`
**File**: `parasite_ai/mind/brain_manager.py`  
**Location**: `_download_worker` inside `start_download` around lines 720–735

#### Before:
```python
                                    with self._lock:
                                        self._current_progress = prog
                                    if progress_callback:
                                        progress_callback(prog)

                                    last_time = now
                                    last_bytes = bytes_downloaded

                    # Download finished - Validate GGUF header
```

#### After:
```python
                                    with self._lock:
                                        self._current_progress = prog
                                    if progress_callback:
                                        progress_callback(prog)
                                        if self._cancel_download_event.is_set():
                                            break

                                    last_time = now
                                    last_bytes = bytes_downloaded

                    if self._cancel_download_event.is_set():
                        logger.info("Download cancelled before completion.")
                        if temp_path.exists():
                            try:
                                temp_path.unlink()
                            except Exception:
                                pass
                        with self._lock:
                            self.state = BrainState.NO_MODEL_PRESENT
                            if self._current_progress:
                                self._current_progress.status = "cancelled"
                        return

                    # Download finished - Validate GGUF header
```

---

### Change 4: Re-entrant Self-Join Prevention in `cancel_download`
**File**: `parasite_ai/mind/brain_manager.py`  
**Location**: `cancel_download` around lines 775–780

#### Before:
```python
    def cancel_download(self) -> None:
        """Signals active streaming download to abort and clean up."""
        self._cancel_download_event.set()
        if self._download_thread and self._download_thread.is_alive():
            self._download_thread.join(timeout=2.0)
```

#### After:
```python
    def cancel_download(self) -> None:
        """Signals active streaming download to abort and clean up."""
        self._cancel_download_event.set()
        if (
            self._download_thread
            and self._download_thread.is_alive()
            and threading.current_thread() is not self._download_thread
        ):
            self._download_thread.join(timeout=2.0)
        with self._lock:
            if self.state == BrainState.DOWNLOADING and (
                not self._download_thread
                or not self._download_thread.is_alive()
                or threading.current_thread() is self._download_thread
            ):
                self.state = BrainState.NO_MODEL_PRESENT
                if self._current_progress:
                    self._current_progress.status = "cancelled"
```

---

### Change 5: State Machine Synchronization in `toggle_browser_only_mode` and `unload_model`
**File**: `parasite_ai/mind/brain_manager.py`  
**Location**: lines 785–836

#### Before:
```python
    def toggle_browser_only_mode(self, enabled: bool) -> None:
        """
        1-Click toggle between Zero-VRAM Browser Offload and Local GPU execution.
        """
        with self._lock:
            if enabled:
                self.unload_model()
                self.mode = BrainMode.BROWSER_OFFLOAD
                self.state = BrainState.READY_BROWSER_OFFLOAD
                self.active_backend = BrowserOffloadBackend(
                    offloader=self.offloader,
                    preferred_browser=self.config.brain.offload.preferred_browser,
                )
                logger.info("Zero-VRAM Browser Offload mode enabled. VRAM consumption set to 0 MB.")
            else:
                self.mode = BrainMode.LOCAL_LLM
                models = self.scan_models()
                valid = [m for m in models if m.is_downloaded and m.is_valid_gguf]
                if valid:
                    self.load_model(valid[0].filename)
                else:
                    self.state = BrainState.NO_MODEL_PRESENT
                    logger.info("Local mode selected but no valid GGUF model present on disk.")

    def load_model(self, filename: Optional[str] = None) -> bool:
        """Loads a valid GGUF model into memory/VRAM."""
        with self._lock:
            fname = filename or self.current_model or self.config.brain.local_model.filename
            fpath = self.models_dir / fname

            if not fpath.is_file() or not validate_gguf_header(fpath):
                logger.warning("Target model %s is missing or has invalid GGUF header.", fname)
                self.state = BrainState.NO_MODEL_PRESENT
                return False

            self.state = BrainState.LOADING
            self.current_model = fname
            success = self._instantiate_local_engine(fpath)
            if success:
                self.mode = BrainMode.LOCAL_LLM
                self.state = BrainState.READY_LOCAL
            return success

    def unload_model(self) -> None:
        """Releases active model from memory and VRAM."""
        with self._lock:
            if self.active_backend:
                self.active_backend.unload()
            if self.mode == BrainMode.LOCAL_LLM or self.state == BrainState.READY_LOCAL:
                self.state = BrainState.MODEL_READY_ON_DISK
```

#### After:
```python
    def toggle_browser_only_mode(self, enabled: bool) -> None:
        """
        1-Click toggle between Zero-VRAM Browser Offload and Local GPU execution.
        """
        with self._lock:
            if enabled:
                self.unload_model()
                self.mode = BrainMode.BROWSER_OFFLOAD
                self.state = BrainState.READY_BROWSER_OFFLOAD
                self._pre_infer_state = BrainState.READY_BROWSER_OFFLOAD
                self.active_backend = BrowserOffloadBackend(
                    offloader=self.offloader,
                    preferred_browser=self.config.brain.offload.preferred_browser,
                )
                logger.info("Zero-VRAM Browser Offload mode enabled. VRAM consumption set to 0 MB.")
            else:
                self.mode = BrainMode.LOCAL_LLM
                models = self.scan_models()
                valid = [m for m in models if m.is_downloaded and m.is_valid_gguf]
                if valid:
                    self.load_model(valid[0].filename)
                    self._pre_infer_state = BrainState.READY_LOCAL
                else:
                    self.state = BrainState.NO_MODEL_PRESENT
                    self._pre_infer_state = BrainState.NO_MODEL_PRESENT
                    logger.info("Local mode selected but no valid GGUF model present on disk.")

    def load_model(self, filename: Optional[str] = None) -> bool:
        """Loads a valid GGUF model into memory/VRAM."""
        with self._lock:
            fname = filename or self.current_model or self.config.brain.local_model.filename
            fpath = self.models_dir / fname

            if not fpath.is_file() or not validate_gguf_header(fpath):
                logger.warning("Target model %s is missing or has invalid GGUF header.", fname)
                self.state = BrainState.NO_MODEL_PRESENT
                self._pre_infer_state = BrainState.NO_MODEL_PRESENT
                return False

            self.state = BrainState.LOADING
            self.current_model = fname
            success = self._instantiate_local_engine(fpath)
            if success:
                self.mode = BrainMode.LOCAL_LLM
                self.state = BrainState.READY_LOCAL
                self._pre_infer_state = BrainState.READY_LOCAL
            return success

    def unload_model(self) -> None:
        """Releases active model from memory and VRAM."""
        with self._lock:
            if self.active_backend:
                self.active_backend.unload()
            if self.mode == BrainMode.LOCAL_LLM or self.state in (BrainState.READY_LOCAL, BrainState.INFERRING):
                self.state = BrainState.MODEL_READY_ON_DISK
                self._pre_infer_state = BrainState.MODEL_READY_ON_DISK
```

---

### Change 6: Thread-Safe State Restoration in `generate()`
**File**: `parasite_ai/mind/brain_manager.py`  
**Location**: `generate` around lines 850–876

#### Before:
```python
        with self._lock:
            if not self.active_backend or not self.active_backend.is_available():
                # Attempt lazy fallback
                if self.mode == BrainMode.MOCK:
                    self.active_backend = MockBackend()
                else:
                    self.active_backend = BrowserOffloadBackend(
                        offloader=self.offloader,
                        preferred_browser=self.config.brain.offload.preferred_browser,
                    )

            prev_state = self.state
            self.state = BrainState.INFERRING

        try:
            return self.active_backend.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop_sequences=stop_sequences,
                json_mode=json_mode,
            )
        finally:
            with self._lock:
                self.state = prev_state
```

#### After:
```python
        with self._lock:
            if not self.active_backend or not self.active_backend.is_available():
                # Attempt lazy fallback
                if self.mode == BrainMode.MOCK:
                    self.active_backend = MockBackend()
                else:
                    self.active_backend = BrowserOffloadBackend(
                        offloader=self.offloader,
                        preferred_browser=self.config.brain.offload.preferred_browser,
                    )

            if self._inferring_count == 0:
                self._pre_infer_state = self.state
            self._inferring_count += 1
            self.state = BrainState.INFERRING

        try:
            return self.active_backend.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop_sequences=stop_sequences,
                json_mode=json_mode,
            )
        finally:
            with self._lock:
                self._inferring_count = max(0, self._inferring_count - 1)
                if self._inferring_count == 0:
                    # All active concurrent inferences completed
                    if self.state == BrainState.INFERRING:
                        if self.mode == BrainMode.BROWSER_OFFLOAD:
                            self.state = BrainState.READY_BROWSER_OFFLOAD
                        elif self._pre_infer_state and self._pre_infer_state != BrainState.INFERRING:
                            self.state = self._pre_infer_state
                        else:
                            self.state = BrainState.READY_LOCAL
                    self._pre_infer_state = None
```

---

### Change 7: Resilient Action Extraction with `JSONDecoder().raw_decode`
**File**: `parasite_ai/mind/brain_manager.py`  
**Location**: `_extract_action_json` around lines 946–990

#### Before:
```python
    @staticmethod
    def _extract_action_json(raw_response: str) -> Optional[Dict[str, Any]]:
        """
        Resilient multi-pass JSON extractor.
        Handles direct JSON, markdown code fences (```json ... ```),
        conversational preambles containing braces, and greedy fallback.
        """
        # Pass 1: Direct JSON parsing
        try:
            parsed = json.loads(raw_response.strip())
            if isinstance(parsed, dict) and "action" in parsed:
                return parsed
        except Exception:
            pass

        # Pass 2: Markdown code fence extraction
        fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw_response, re.IGNORECASE)
        if fence_match:
            try:
                parsed = json.loads(fence_match.group(1).strip())
                if isinstance(parsed, dict) and "action" in parsed:
                    return parsed
            except Exception:
                pass

        # Pass 3: Greedy match for single JSON object
        try:
            match = re.search(r"\{[\s\S]*\}", raw_response)
            if match:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict) and "action" in parsed:
                    return parsed
        except Exception:
            pass

        # Pass 4: Find all potential JSON objects
        for candidate in re.findall(r"\{[\s\S]*?\}", raw_response):
            try:
                parsed = json.loads(candidate.strip())
                if isinstance(parsed, dict) and "action" in parsed:
                    return parsed
            except Exception:
                pass

        return None
```

#### After:
```python
    @staticmethod
    def _extract_action_json(raw_response: str) -> Optional[Dict[str, Any]]:
        """
        Resilient multi-pass JSON extractor.
        Handles direct JSON, markdown code fences (```json ... ```),
        conversational preambles containing braces, and greedy fallback.
        """
        # Pass 1: Direct JSON parsing
        try:
            parsed = json.loads(raw_response.strip())
            if isinstance(parsed, dict) and "action" in parsed:
                return parsed
        except Exception:
            pass

        # Pass 2: Markdown code fence extraction (supporting 3+ backticks and preambles)
        for fence in re.finditer(r"`{3,}(?:json|markdown)?\s*([\s\S]*?)`{3,}", raw_response, re.IGNORECASE):
            candidate = fence.group(1).strip()
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict) and "action" in parsed:
                    return parsed
            except Exception:
                pass
            # Candidate inside fence might still have conversational text or nested objects
            dec = json.JSONDecoder()
            start = 0
            while True:
                idx = candidate.find('{', start)
                if idx == -1:
                    break
                try:
                    obj, _ = dec.raw_decode(candidate[idx:])
                    if isinstance(obj, dict) and "action" in obj:
                        return obj
                except Exception:
                    pass
                start = idx + 1

        # Pass 3: Search using JSONDecoder.raw_decode for any valid JSON object with "action"
        dec = json.JSONDecoder()
        start = 0
        while True:
            idx = raw_response.find('{', start)
            if idx == -1:
                break
            try:
                obj, _ = dec.raw_decode(raw_response[idx:])
                if isinstance(obj, dict) and "action" in obj:
                    return obj
            except Exception:
                pass
            start = idx + 1

        return None
```

---

## Verification Commands
After applying these changes to `parasite_ai/mind/brain_manager.py`, run:
1. `uv run pytest tests/test_stress_concurrency.py`
2. `uv run pytest tests/test_stress_m1.py`
3. `uv run pytest` (full suite across 111 tests)
Expected result: `111 passed in ~9.6s (100% pass)`
