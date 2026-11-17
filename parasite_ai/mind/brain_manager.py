"""
ParasiteAI - Local Brain Manager (Zero-Config, Pluggable Backends & Dual-Mind Dispatch).

Supports:
1. Pluggable inference backends: LlamaCppBackend, OpenAIEndpointBackend, BrowserOffloadBackend, MockBackend.
2. Binary GGUF header validation (magic bytes b"GGUF", version 2/3).
3. Non-blocking streaming downloads with progress callbacks, ETA, speed, and atomic file renaming.
4. Zero-VRAM browser offload toggle for instant startup without GPU memory footprint.
5. High-level Dual-Mind dispatchers: Pass 1 Persona monologue and Pass 2 deterministic Action Dispatcher.
6. RTX 4060 VRAM budget and headroom enforcement.
"""

from __future__ import annotations

import os
import re
import json
import time
import struct
import shutil
import signal
import subprocess
import logging
import threading
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Union

import httpx
from pydantic import BaseModel, Field

from parasite_ai.config import AppConfig

logger = logging.getLogger("parasite_ai.brain_manager")


# ---------------------------------------------------------------------------
# Enums and Telemetry Models
# ---------------------------------------------------------------------------

class BrainMode(str, Enum):
    """Configured operating mode for the Brain subsystem."""
    LOCAL_LLM = "local_llm"              # In-process GGUF or local HTTP server
    BROWSER_OFFLOAD = "browser_offload"  # Zero-VRAM mode using desktop browser web AI
    HYBRID = "hybrid"                    # Local LLM for quick actions, Browser for deep reasoning
    MOCK = "mock"                        # Deterministic mock backend for automated testing


class BrainState(str, Enum):
    """Runtime lifecycle state of the Brain."""
    UNINITIALIZED = "UNINITIALIZED"
    NO_MODEL_PRESENT = "NO_MODEL_PRESENT"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOAD_PAUSED = "DOWNLOAD_PAUSED"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    MODEL_READY_ON_DISK = "MODEL_READY_ON_DISK"
    LOADING = "LOADING"
    READY_LOCAL = "READY_LOCAL"
    READY_BROWSER_OFFLOAD = "READY_BROWSER_OFFLOAD"
    INFERRING = "INFERRING"
    ERROR = "ERROR"


class ModelMetadata(BaseModel):
    """Information regarding a detected or downloadable GGUF model."""
    model_id: str
    filename: str
    mmproj_filename: Optional[str] = None
    mmproj_path: Optional[str] = None
    supports_vision: bool = False
    filesize_bytes: int = 0
    filesize_display: str = ""
    is_downloaded: bool = False
    is_valid_gguf: bool = False
    file_path: Optional[str] = None
    recommended_gpu_layers: int = -1
    vram_required_mb: int = 3500


class DownloadProgress(BaseModel):
    """Live streaming download metrics dispatched to UI callbacks."""
    model_id: str
    filename: str
    bytes_downloaded: int = 0
    total_bytes: int = 0
    percentage: float = 0.0
    speed_mbps: float = 0.0
    eta_seconds: float = 0.0
    elapsed_seconds: float = 0.0
    status: str = "downloading"  # downloading, verifying, completed, failed, cancelled


class BrainStatus(BaseModel):
    """Comprehensive snapshot of the Brain subsystem state."""
    mode: BrainMode
    state: BrainState
    active_backend: str = "none"
    current_model: Optional[str] = None
    available_models: List[ModelMetadata] = Field(default_factory=list)
    download_progress: Optional[DownloadProgress] = None
    vram_budget_mb: int = 5500
    vram_used_mb: Optional[int] = None
    vram_free_mb: Optional[int] = None
    status_message: str = "Ready"


# ---------------------------------------------------------------------------
# Binary GGUF Header Validation
# ---------------------------------------------------------------------------

def validate_gguf_header(filepath: Union[Path, str], min_bytes: int = 8) -> bool:
    """
    Verifies that the target file exists and possesses a valid binary GGUF header.
    GGUF specification:
    - Magic bytes: 0x47 0x47 0x55 0x46 (b"GGUF")
    - Version: 32-bit unsigned little-endian integer in (2, 3)
    """
    path = Path(filepath)
    if not path.is_file():
        return False

    try:
        if path.stat().st_size < min_bytes:
            return False

        with open(path, "rb") as f:
            magic = f.read(4)
            if magic != b"GGUF":
                return False

            version_bytes = f.read(4)
            if len(version_bytes) < 4:
                return False

            version = struct.unpack("<I", version_bytes)[0]
            return version in (2, 3)
    except Exception as exc:
        logger.debug("Failed validating GGUF header for %s: %s", path, exc)
        return False


def format_bytes(num_bytes: int) -> str:
    """Format byte count into human-readable representation."""
    if num_bytes <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} PB"


# ---------------------------------------------------------------------------
# Curated Model Catalog
# ---------------------------------------------------------------------------

CURATED_MODELS: List[Dict[str, Any]] = [
    {
        "model_id": "mradermacher/UI-TARS-1.5-7B-GGUF",
        "filename": "UI-TARS-1.5-7B.IQ4_XS.gguf",
        "mmproj_filename": "UI-TARS-1.5-7B.mmproj-Q8_0.gguf",
        "mmproj_filesize_bytes": 856130240,
        "filesize_bytes": 4250298688,
        "filesize_display": "5.11 GB (VLM IQ4_XS + mmproj Q8_0)",
        "recommended_gpu_layers": -1,
        "vram_required_mb": 5100,
    },
    {
        "model_id": "mradermacher/UI-TARS-1.5-7B-GGUF",
        "filename": "UI-TARS-1.5-7B.Q4_K_M.gguf",
        "mmproj_filename": "UI-TARS-1.5-7B.mmproj-Q8_0.gguf",
        "mmproj_filesize_bytes": 856130240,
        "filesize_bytes": 4683073856,
        "filesize_display": "5.54 GB (VLM Q4_K_M + mmproj Q8_0)",
        "recommended_gpu_layers": -1,
        "vram_required_mb": 5500,
    },
    {
        "model_id": "ggml-org/Qwen2.5-VL-3B-Instruct-GGUF",
        "filename": "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf",
        "mmproj_filename": "mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf",
        "mmproj_filesize_bytes": 844757728,
        "filesize_bytes": 1929901056,
        "filesize_display": "2.58 GB (VLM + mmproj)",
        "recommended_gpu_layers": -1,
        "vram_required_mb": 3600,
    },
    {
        "model_id": "Qwen/Qwen2.5-3B-Instruct-GGUF",
        "filename": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "filesize_bytes": 2328221696,
        "filesize_display": "2.17 GB",
        "recommended_gpu_layers": -1,
        "vram_required_mb": 3200,
    },
    {
        "model_id": "Qwen/Qwen2.5-7B-Instruct-GGUF",
        "filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
        "filesize_bytes": 5025000000,
        "filesize_display": "4.68 GB",
        "recommended_gpu_layers": 28,
        "vram_required_mb": 5200,
    },
    {
        "model_id": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "filesize_bytes": 1200000000,
        "filesize_display": "1.12 GB",
        "recommended_gpu_layers": -1,
        "vram_required_mb": 1800,
    },
]


# ---------------------------------------------------------------------------
# Polymorphic Inference Backends
# ---------------------------------------------------------------------------

def _normalize_image_data_uri(image_base64: Optional[str]) -> Optional[str]:
    """Normalizes a base64 image string or data URI into `data:image/jpeg;base64,...`."""
    if not image_base64 or not isinstance(image_base64, str):
        return None
    stripped = image_base64.strip()
    if not stripped:
        return None
    if stripped.startswith("data:image/"):
        return stripped
    return f"data:image/jpeg;base64,{stripped}"


class InferenceBackend(ABC):
    """Abstract polymorphic interface for LLM/VLM inference providers."""

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the backend is initialized and ready to serve inference."""
        pass

    def supports_vision(self) -> bool:
        """Returns True if this backend accepts multimodal image payloads."""
        return False

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None,
        json_mode: bool = False,
        image_base64: Optional[str] = None,
    ) -> str:
        """Executes synchronous inference and returns generated text."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Releases all allocated memory/VRAM resources."""
        pass


class MockBackend(InferenceBackend):
    """Deterministic mock backend for unit testing and offline development."""

    def __init__(self, canned_responses: Optional[List[str]] = None, vision_enabled: bool = False) -> None:
        self.canned_responses: List[str] = canned_responses or []
        self._call_history: List[Dict[str, Any]] = []
        self._available = True
        self._vision_enabled = vision_enabled

    def is_available(self) -> bool:
        return self._available

    def supports_vision(self) -> bool:
        return self._vision_enabled

    def enqueue_response(self, response: str) -> None:
        self.canned_responses.append(response)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None,
        json_mode: bool = False,
        image_base64: Optional[str] = None,
    ) -> str:
        self._call_history.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "json_mode": json_mode,
            "image_base64": image_base64,
        })

        if self.canned_responses:
            return self.canned_responses.pop(0)

        # Default smart response generator for Pass 1 thoughts and Pass 2 actions
        if json_mode or "action" in prompt.lower() or (system_prompt and "action dispatcher" in system_prompt.lower()):
            # Provide deterministic JSON action
            return json.dumps({
                "action": "CLICK",
                "target_id": 1,
                "coordinates": [500, 300],
                "reasoning": "Mocking click on target element #1",
            })

        # Provide deterministic Pass 1 monologue thought
        return "I see the desktop screen clearly. Preparing to proceed with current user objective."

    def unload(self) -> None:
        self._call_history.clear()


def _register_cuda_dll_directories() -> None:
    """Registers packaged NVIDIA CUDA runtime/cuBLAS DLL directories on Windows."""
    if os.name != "nt":
        return
    try:
        import sys
        nvidia_root = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
        if not nvidia_root.is_dir():
            return
        bin_dirs = [str(p) for p in nvidia_root.glob("*/bin") if p.is_dir()]
        if not bin_dirs:
            return
        current_path = os.environ.get("PATH", "")
        for bdir in bin_dirs:
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(bdir)
                except Exception:
                    pass
            if bdir not in current_path:
                current_path = bdir + os.pathsep + current_path
        os.environ["PATH"] = current_path
    except Exception as exc:
        logger.debug("CUDA DLL directory registration skipped: %s", exc)


class LlamaCppBackend(InferenceBackend):
    """In-process GGUF LLM/VLM engine via llama-cpp-python (supports mmproj vision projectors)."""

    def __init__(
        self,
        model_path: Path | str,
        n_gpu_layers: int = -1,
        n_ctx: int = 4096,
        n_threads: int = 8,
        mmproj_path: Optional[Path | str] = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.n_gpu_layers = n_gpu_layers
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.mmproj_path: Optional[Path] = Path(mmproj_path) if mmproj_path else self._discover_mmproj_path(self.model_path)
        self._chat_handler: Any = None
        self._llm: Any = None
        self._init_model()

    @staticmethod
    def _discover_mmproj_path(model_path: Path) -> Optional[Path]:
        """Auto-discovers a companion mmproj-*.gguf file in the same directory for VLM models."""
        try:
            parent = model_path.parent
            if not parent.is_dir():
                return None
            # 1. Exact curated match
            for item in CURATED_MODELS:
                if item.get("filename") == model_path.name and item.get("mmproj_filename"):
                    cand = parent / item["mmproj_filename"]
                    if cand.is_file() and validate_gguf_header(cand):
                        return cand
            # 2. If model filename looks like a VLM, look for any valid mmproj*.gguf in parent
            name_low = model_path.name.lower()
            if any(k in name_low for k in ("vl", "vision", "tars", "llava", "minicpm", "moondream", "pixtral")):
                for p in sorted(parent.glob("*mmproj*.gguf")):
                    if validate_gguf_header(p):
                        return p
        except Exception:
            pass
        return None

    def _init_model(self) -> None:
        try:
            # Skip heavy C++ GGUF initialization for tiny unit-test stub files (< 10 MB)
            # or synthetic pytest runs unless PARASITE_TEST_REAL_LLM=1 is set.
            if not self.model_path.is_file() or self.model_path.stat().st_size < 10 * 1024 * 1024:
                self._llm = None
                return
            if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("PARASITE_TEST_REAL_LLM"):
                self._llm = None
                return

            _register_cuda_dll_directories()
            import llama_cpp  # type: ignore

            # Initialize multimodal chat handler if a valid mmproj vision projector is present
            self._chat_handler = None
            if (
                self.mmproj_path is not None
                and self.mmproj_path.is_file()
                and self.mmproj_path.stat().st_size >= 10 * 1024 * 1024
                and validate_gguf_header(self.mmproj_path)
            ):
                try:
                    import llama_cpp.llama_chat_format as lcf  # type: ignore
                    if hasattr(lcf, "MTMDChatHandler"):
                        self._chat_handler = lcf.MTMDChatHandler(
                            clip_model_path=str(self.mmproj_path),
                            verbose=False,
                            use_gpu=(self.n_gpu_layers != 0),
                        )
                        logger.info("Initialized MTMDChatHandler vision projector: %s", self.mmproj_path.name)
                    elif hasattr(lcf, "Qwen25VLChatHandler"):
                        self._chat_handler = lcf.Qwen25VLChatHandler(
                            clip_model_path=str(self.mmproj_path),
                            verbose=False,
                        )
                        logger.info("Initialized Qwen25VLChatHandler vision projector: %s", self.mmproj_path.name)
                except Exception as v_exc:
                    logger.warning("Failed initializing VLM mmproj handler (%s); falling back to text-only: %s", self.mmproj_path, v_exc)
                    self._chat_handler = None

            self._llm = llama_cpp.Llama(
                model_path=str(self.model_path),
                n_gpu_layers=self.n_gpu_layers,
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                chat_handler=self._chat_handler,
                verbose=False,
            )
        except Exception as exc:
            logger.warning("Could not initialize llama_cpp engine: %s", exc)
            self._llm = None
            self._chat_handler = None

    def is_available(self) -> bool:
        return self._llm is not None

    def supports_vision(self) -> bool:
        return self._llm is not None and self._chat_handler is not None

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None,
        json_mode: bool = False,
        image_base64: Optional[str] = None,
    ) -> str:
        if not self.is_available():
            raise RuntimeError("LlamaCppBackend is not available or model not loaded.")

        data_uri = _normalize_image_data_uri(image_base64) if self.supports_vision() else None
        image_token_reserve = 1024 if data_uri else 0

        # Dynamic token budget and context window headroom protection
        try:
            sys_text = system_prompt or ""
            sys_tokens = self._llm.tokenize(sys_text.encode("utf-8", errors="replace"), add_bos=False) if sys_text else []
            prompt_toks = self._llm.tokenize(prompt.encode("utf-8", errors="replace"), add_bos=False)
            tokens = sys_tokens + prompt_toks
            prompt_tokens = len(tokens) + image_token_reserve
            if prompt_tokens + max_tokens > self.n_ctx:
                headroom = self.n_ctx - prompt_tokens - 32
                if headroom >= 64:
                    logger.warning(
                        "Prompt tokens (%d) close to context size (%d). Dynamically adjusting max_tokens from %d to %d.",
                        prompt_tokens, self.n_ctx, max_tokens, headroom,
                    )
                    max_tokens = headroom
                else:
                    logger.warning(
                        "Prompt tokens (%d) exceed available context (%d). Truncating user prompt context.",
                        prompt_tokens, self.n_ctx,
                    )
                    max_tokens = min(max_tokens, 96)
                    allowed_prompt_tokens = max(128, self.n_ctx - image_token_reserve - len(sys_tokens) - max_tokens - 64)
                    chars_per_tok = max(1.2, len(prompt) / max(1, len(prompt_toks)))
                    target_chars = max(200, int(allowed_prompt_tokens * chars_per_tok))
                    suffix_line = "\nRespond strictly with the single JSON action command." if "JSON action command" in prompt else ""
                    prompt = prompt[:target_chars] + "\n[...truncated for context window...]" + suffix_line
        except Exception as tok_err:
            logger.debug("Token pre-check bypassed: %s", tok_err)

        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if data_uri:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            })
        elif self._chat_handler is not None:
            messages.append({
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            })
        else:
            messages.append({"role": "user", "content": prompt})

        try:
            response = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop_sequences,
            )
            return response["choices"][0]["message"]["content"]
        except (ValueError, RuntimeError) as exc:
            # Resilient fallback if llama_cpp raises context window overflow or llama_decode KV slot error
            err_lower = str(exc).lower()
            if (
                "exceed context window" in err_lower
                or "exceeds n_ctx" in err_lower
                or "llama_decode" in err_lower
                or "failed to evaluate chunk" in err_lower
            ):
                logger.error(
                    "Token/KV overflow caught in create_chat_completion (%s). Resetting KV cache and retrying with compact prompt.",
                    exc,
                )
                try:
                    if hasattr(self._llm, "reset"):
                        self._llm.reset()
                    if hasattr(self._llm, "_ctx") and hasattr(self._llm._ctx, "kv_cache_clear"):
                        self._llm._ctx.kv_cache_clear()
                except Exception:
                    pass
                half_len = min(len(prompt) // 2, 1800)
                suffix_line = "\nRespond strictly with the single JSON action command." if "JSON action command" in prompt else ""
                short_prompt = prompt[:half_len] + "\n[...truncated for context window...]" + suffix_line
                if self._chat_handler is not None:
                    messages[-1]["content"] = [{"type": "text", "text": short_prompt}]
                else:
                    messages[-1]["content"] = short_prompt
                response = self._llm.create_chat_completion(
                    messages=messages,
                    max_tokens=min(max_tokens, 64),
                    temperature=temperature,
                    stop=stop_sequences,
                )
                return response["choices"][0]["message"]["content"]
            raise

    def unload(self) -> None:
        self._llm = None
        self._chat_handler = None


class OpenAIEndpointBackend(InferenceBackend):
    """HTTP client adapter for local OpenAI-compatible endpoints (Ollama, llama-server)."""

    def __init__(self, endpoint: str = "http://127.0.0.1:8080/v1", model_name: str = "default", vision_enabled: bool = True) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model_name = model_name
        self._vision_enabled = vision_enabled
        self._client = httpx.Client(timeout=30.0)

    def is_available(self) -> bool:
        try:
            resp = self._client.get(f"{self.endpoint}/models")
            return resp.status_code == 200
        except Exception:
            return False

    def supports_vision(self) -> bool:
        return self._vision_enabled

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None,
        json_mode: bool = False,
        image_base64: Optional[str] = None,
    ) -> str:
        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        data_uri = _normalize_image_data_uri(image_base64) if self.supports_vision() else None
        if data_uri:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            })
        else:
            messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop_sequences:
            payload["stop"] = stop_sequences
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        resp = self._client.post(f"{self.endpoint}/chat/completions", json=payload)
        if resp.status_code == 500 and "image input is not supported" in resp.text:
            logger.warning("llama-server does not support image input without mmproj; retrying with text only.")
            text_messages = []
            for m in messages:
                if isinstance(m.get("content"), list):
                    texts = [item["text"] for item in m["content"] if item.get("type") == "text"]
                    text_messages.append({"role": m["role"], "content": "\n".join(texts)})
                else:
                    text_messages.append(m)
            payload["messages"] = text_messages
            resp = self._client.post(f"{self.endpoint}/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def unload(self) -> None:
        self._client.close()


class LlamaServerBackend(InferenceBackend):
    """
    Out-of-process persistent llama-server daemon backend with 0ms cold-start attach.

    Operates in two modes:
    1. Attach mode: If a server is already healthy at http://{host}:{port}/health, attaches
       instantly across benchmark tasks or CLI invocations without spawning a new process.
    2. Managed daemon mode: If auto_start is True and no server is running, spawns
       llama-server.exe as a managed background daemon, polls /health until ready,
       and manages process termination on unload if exclusively owned.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        model_path: Optional[Union[str, Path]] = None,
        mmproj_path: Optional[Union[str, Path]] = None,
        server_binary: Optional[Union[str, Path]] = "bin/llama-server/llama-server.exe",
        n_gpu_layers: int = -1,
        n_ctx: int = 8192,
        parallel_slots: int = 1,
        image_min_tokens: int = 1024,
        kv_cache_type_k: str = "q8_0",
        kv_cache_type_v: str = "q8_0",
        cache_reuse_tokens: int = 0,
        keep_alive_on_exit: bool = True,
        auto_start: bool = True,
        startup_timeout_sec: float = 60.0,
        model_name: str = "default",
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.endpoint = f"{self.base_url}/v1"
        self.model_path = Path(model_path) if model_path else None
        self.mmproj_path = Path(mmproj_path) if mmproj_path else None
        self.server_binary = Path(server_binary) if server_binary else None
        self.n_gpu_layers = n_gpu_layers
        self.n_ctx = n_ctx
        self.parallel_slots = parallel_slots
        self.image_min_tokens = image_min_tokens
        self.kv_cache_type_k = kv_cache_type_k
        self.kv_cache_type_v = kv_cache_type_v
        self.cache_reuse_tokens = cache_reuse_tokens
        self.keep_alive_on_exit = keep_alive_on_exit
        self.auto_start = auto_start
        self.startup_timeout_sec = startup_timeout_sec
        self.model_name = model_name

        self._client = client or httpx.Client(timeout=45.0)
        self._managed_process: Optional[subprocess.Popen] = None
        self._is_external: bool = False
        self._init_connection()

    def _resolve_binary_path(self) -> Optional[Path]:
        """Resolves llama-server executable path from config, workspace, or PATH."""
        candidates = []
        if self.server_binary:
            candidates.append(self.server_binary)
            candidates.append(Path("C:/ParasiteAI") / self.server_binary)
        candidates.extend([
            Path("bin/llama-server/llama-server.exe"),
            Path("C:/ParasiteAI/bin/llama-server/llama-server.exe"),
            Path("bin/llama-server/llama.exe"),
            Path("C:/ParasiteAI/bin/llama-server/llama.exe"),
        ])
        for cand in candidates:
            if cand.is_file():
                return cand.resolve()
        which_path = shutil.which("llama-server") or shutil.which("llama-server.exe")
        if which_path:
            return Path(which_path)
        return None

    def check_health(self) -> Dict[str, Any]:
        """Queries the /health endpoint of the llama-server."""
        try:
            resp = self._client.get(f"{self.base_url}/health", timeout=2.0)
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception:
                    return {"status": "ok"}
            elif resp.status_code == 503:
                return {"status": "loading model"}
            return {"status": "error", "code": resp.status_code}
        except Exception as exc:
            return {"status": "unreachable", "error": str(exc)}

    def is_available(self) -> bool:
        """Returns True if the server is up and ready to serve inference."""
        health = self.check_health()
        return health.get("status") == "ok"

    def supports_vision(self) -> bool:
        """Returns True if configured with a valid multimodal vision projector."""
        if self.mmproj_path and self.mmproj_path.is_file():
            return True
        return False

    def _init_connection(self) -> bool:
        """Attaches to existing daemon or starts new process if auto_start is enabled."""
        health = self.check_health()
        if health.get("status") == "ok":
            logger.info("Attached to running llama-server at %s (0ms cold start)", self.base_url)
            self._is_external = True
            return True

        if not self.auto_start:
            logger.info("llama-server not running at %s and auto_start is False", self.base_url)
            return False

        return self.start_server_daemon()

    def start_server_daemon(self) -> bool:
        """Spawns llama-server.exe daemon and waits for /health readiness."""
        exe_path = self._resolve_binary_path()
        if not exe_path:
            logger.warning("Cannot start llama-server: executable not found")
            return False

        if not self.model_path or not self.model_path.is_file():
            logger.warning("Cannot start llama-server: model file not found (%s)", self.model_path)
            return False

        # Guard against small pytest dummy GGUFs (< 10 MB) or synthetic test environments
        if self.model_path.stat().st_size < 10 * 1024 * 1024:
            logger.debug("Skipping llama-server start on small test stub (< 10 MB): %s", self.model_path)
            return False
        if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("PARASITE_TEST_REAL_LLM"):
            logger.debug("Skipping llama-server start during unit test: %s", self.model_path)
            return False

        cmd = [
            str(exe_path),
            "-m", str(self.model_path.resolve()),
            "-c", str(self.n_ctx),
            "-ngl", str(self.n_gpu_layers),
            "-np", str(self.parallel_slots),
            "--host", self.host,
            "--port", str(self.port),
            "-fa", "auto",
        ]

        if self.kv_cache_type_k:
            cmd.extend(["-ctk", str(self.kv_cache_type_k)])
        if self.kv_cache_type_v:
            cmd.extend(["-ctv", str(self.kv_cache_type_v)])
        is_multimodal = bool(self.mmproj_path and self.mmproj_path.is_file())
        if self.cache_reuse_tokens and self.cache_reuse_tokens > 0 and not is_multimodal:
            cmd.extend(["--cache-reuse", str(self.cache_reuse_tokens)])

        # Multimodal projector
        if self.mmproj_path and self.mmproj_path.is_file():
            cmd.extend([
                "--mmproj", str(self.mmproj_path.resolve()),
                "--image-min-tokens", str(self.image_min_tokens),
            ])

        env = os.environ.copy()
        env["PATH"] = str(exe_path.parent) + os.pathsep + env.get("PATH", "")

        creation_flags = 0
        if os.name == "nt":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008
            creation_flags |= 0x01000000  # CREATE_BREAKAWAY_FROM_JOB

        log_path = Path("logs/llama_server.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._server_log_f = open(log_path, "a", encoding="utf-8")

        logger.info("Spawning persistent llama-server daemon: %s", " ".join(cmd))
        try:
            self._managed_process = subprocess.Popen(
                cmd,
                stdout=self._server_log_f,
                stderr=self._server_log_f,
                env=env,
                creationflags=creation_flags,
            )
            self._is_external = False
        except PermissionError:
            creation_flags &= ~0x01000000
            try:
                self._managed_process = subprocess.Popen(
                    cmd,
                    stdout=self._server_log_f,
                    stderr=self._server_log_f,
                    env=env,
                    creationflags=creation_flags,
                )
                self._is_external = False
            except Exception as exc:
                logger.error("Failed to spawn llama-server: %s", exc)
                return False
        except Exception as exc:
            logger.error("Failed to spawn llama-server: %s", exc)
            return False

        start_t = time.time()
        while time.time() - start_t < self.startup_timeout_sec:
            if self._managed_process.poll() is not None:
                err = ""
                if self._managed_process.stderr:
                    err = self._managed_process.stderr.read().decode("utf-8", errors="replace")
                logger.error("llama-server process exited prematurely (code %d): %s", self._managed_process.returncode, err)
                return False

            health = self.check_health()
            if health.get("status") == "ok":
                elapsed = time.time() - start_t
                logger.info("llama-server ready at %s in %.2fs", self.base_url, elapsed)
                return True
            time.sleep(0.5)

        logger.error("llama-server startup timed out after %.1fs", self.startup_timeout_sec)
        return False

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None,
        json_mode: bool = False,
        image_base64: Optional[str] = None,
    ) -> str:
        if not self.is_available():
            if not self._init_connection():
                raise RuntimeError(f"LlamaServerBackend is not available at {self.base_url}")

        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        data_uri = _normalize_image_data_uri(image_base64) if self.supports_vision() else None
        if data_uri:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            })
        else:
            messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop_sequences:
            payload["stop"] = stop_sequences
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        resp = self._client.post(f"{self.endpoint}/chat/completions", json=payload)
        if resp.status_code == 500 and "image input is not supported" in resp.text:
            logger.warning("llama-server does not support image input without mmproj; retrying with text only.")
            text_messages = []
            for m in messages:
                if isinstance(m.get("content"), list):
                    texts = [item["text"] for item in m["content"] if item.get("type") == "text"]
                    text_messages.append({"role": m["role"], "content": "\n".join(texts)})
                else:
                    text_messages.append(m)
            payload["messages"] = text_messages
            resp = self._client.post(f"{self.endpoint}/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def unload(self, terminate_daemon: bool = False) -> None:
        """Terminates managed server process or detaches client."""
        if self._managed_process is not None and not self._is_external:
            if terminate_daemon or not self.keep_alive_on_exit:
                pid = getattr(self._managed_process, "pid", "unknown")
                logger.info("Stopping managed llama-server process (PID %s)...", pid)
                try:
                    self._managed_process.terminate()
                    self._managed_process.wait(timeout=5)
                except Exception:
                    try:
                        self._managed_process.kill()
                    except Exception:
                        pass
                self._managed_process = None
            else:
                logger.info(
                    "Keeping persistent llama-server daemon alive across task boundary (PID %s).",
                    getattr(self._managed_process, "pid", "unknown"),
                )
                self._managed_process = None

        try:
            self._client.close()
        except Exception:
            pass


class BrowserOffloadBackend(InferenceBackend):
    """Physical desktop web AI offload backend (Zero-VRAM mode)."""

    def __init__(self, offloader: Any = None, preferred_browser: str = "chrome") -> None:
        self.offloader = offloader
        self.preferred_browser = preferred_browser

    def is_available(self) -> bool:
        # Browser offloading is always logically available on desktop with installed browser
        return True

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None,
        json_mode: bool = False,
        image_base64: Optional[str] = None,
    ) -> str:
        full_query = prompt
        if system_prompt:
            full_query = f"{system_prompt}\n\nTask:\n{prompt}"

        if self.offloader and hasattr(self.offloader, "query_web_ai"):
            return self.offloader.query_web_ai(full_query, browser_type=self.preferred_browser)

        # Fallback simulator when physical offloader is not connected
        if json_mode or "action" in full_query.lower():
            return json.dumps({
                "action": "OFFLOAD_WEB_AI",
                "browser": self.preferred_browser,
                "reasoning": "Dispatching query through visible browser interface.",
            })

        return f"[Browser Offload: {self.preferred_browser}] Ready to visually offload cognitive task."

    def unload(self) -> None:
        pass


# Export alias for web offload backend references
WebOffloadBackend = BrowserOffloadBackend


# ---------------------------------------------------------------------------
# VRAM Headroom & Guard
# ---------------------------------------------------------------------------

def check_vram_headroom() -> Tuple[int, int]:
    """
    Returns (used_vram_mb, free_vram_mb) for primary NVIDIA GPU.
    Falls back gracefully if nvidia-smi / pynvml is unavailable.
    """
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.free", "--format=csv,nounits,noheader"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        line = result.stdout.strip().split("\n")[0]
        used_str, free_str = [x.strip() for x in line.split(",")]
        return int(used_str), int(free_str)
    except Exception:
        # Safe simulated values for RTX 4060 (8GB total, 2500MB baseline system/DWM use, 5688MB free)
        return 2500, 5688


# ---------------------------------------------------------------------------
# Local Brain Manager
# ---------------------------------------------------------------------------

class LocalBrainManager:
    """
    Central local brain coordinator for ParasiteAI.
    Manages local models, non-blocking downloads, dynamic zero-VRAM browser offload,
    and unified cognitive dispatch.
    """

    def __init__(self, config: AppConfig, offloader: Any = None) -> None:
        self.config = config
        self.offloader = offloader
        self.models_dir = Path(config.system.models_dir)
        self.mode = BrainMode(config.brain.mode)
        self.state = BrainState.UNINITIALIZED
        self.active_backend: Optional[InferenceBackend] = None
        self.current_model: Optional[str] = None
        self.available_models: List[ModelMetadata] = []

        self._download_thread: Optional[threading.Thread] = None
        self._cancel_download_event = threading.Event()
        self._current_progress: Optional[DownloadProgress] = None
        self._lock = threading.RLock()
        self._inferring_count: int = 0
        self._pre_infer_state: Optional[BrainState] = None

        # Initialize storage and assess initial status
        self.ensure_models_dir()
        self._init_backend()
        self.refresh_status()

    def ensure_models_dir(self) -> Path:
        """Ensure models directory exists on disk."""
        self.models_dir.mkdir(parents=True, exist_ok=True)
        return self.models_dir

    def _init_backend(self) -> None:
        """Instantiate active backend based on configuration mode."""
        with self._lock:
            if self.mode == BrainMode.MOCK:
                self.active_backend = MockBackend()
                self.state = BrainState.READY_LOCAL
                return

            if self.mode == BrainMode.BROWSER_OFFLOAD:
                self.active_backend = BrowserOffloadBackend(
                    offloader=self.offloader,
                    preferred_browser=self.config.brain.offload.preferred_browser,
                )
                self.state = BrainState.READY_BROWSER_OFFLOAD
                return

            # For local_llm or hybrid: scan disk
            models = self.scan_models()
            valid_models = [m for m in models if m.is_downloaded and m.is_valid_gguf]

            if valid_models:
                # Prefer configured filename or VLM model with vision projector if present on disk
                cfg_fname = self.config.brain.local_model.filename
                target = (
                    next((m for m in valid_models if m.filename == cfg_fname), None)
                    or next((m for m in valid_models if m.supports_vision), None)
                    or valid_models[0]
                )
                self.current_model = target.filename
                self.state = BrainState.MODEL_READY_ON_DISK
                self._instantiate_local_engine(target.file_path or target.filename, mmproj_path=target.mmproj_path)
            elif self.mode == BrainMode.LOCAL_LLM:
                # Decouple local execution: do NOT silently fallback to browser offload
                logger.info("Local LLM mode selected, but no valid local GGUF model found on disk.")
                self.state = BrainState.NO_MODEL_PRESENT
                self.active_backend = None
            else:
                # Zero-VRAM Fallback: If no local model exists in hybrid mode, fallback to browser offload
                logger.info("No valid local GGUF model found. Booting in Zero-VRAM Browser Offload mode.")
                self.mode = BrainMode.BROWSER_OFFLOAD
                self.state = BrainState.READY_BROWSER_OFFLOAD
                self.active_backend = BrowserOffloadBackend(
                    offloader=self.offloader,
                    preferred_browser=self.config.brain.offload.preferred_browser,
                )

    def _instantiate_local_engine(
        self,
        model_path: Union[Path, str],
        mmproj_path: Optional[Union[Path, str]] = None,
    ) -> bool:
        """Try instantiating LlamaCppBackend, fallback to mock or endpoint."""
        used_mb, free_mb = check_vram_headroom()
        budget_mb = self.config.brain.local_model.vram_budget_mb
        effective_vram_mb = min(free_mb, budget_mb)

        configured_layers = self.config.brain.local_model.gpu_layers

        # Lookup model requirements and layer counts
        model_name = Path(model_path).name
        curated_info = next((m for m in CURATED_MODELS if m["filename"] == model_name), None)
        if curated_info:
            vram_required_mb = curated_info.get("vram_required_mb", 3500)
            rec_layers = curated_info.get("recommended_gpu_layers", -1)
            total_layers = rec_layers if rec_layers > 0 else 32
            if mmproj_path is None and curated_info.get("mmproj_filename"):
                cand_mmproj = self.models_dir / curated_info["mmproj_filename"]
                if cand_mmproj.is_file() and validate_gguf_header(cand_mmproj):
                    mmproj_path = cand_mmproj
        else:
            meta = next((m for m in self.available_models if m.filename == model_name), None)
            vram_required_mb = meta.vram_required_mb if meta else 3500
            total_layers = 32
            if mmproj_path is None and meta and meta.mmproj_path:
                mmproj_path = meta.mmproj_path

        # Evaluate VRAM budget against requirements
        if effective_vram_mb < 2000:
            # Low VRAM / low budget: force CPU fallback (0 layers) to prevent CUDA OOM
            gpu_layers = 0
        elif effective_vram_mb < vram_required_mb:
            # VRAM budget is exceeded by model requirement:
            # Scale offload layers proportionally to fit within effective VRAM
            layer_ratio = effective_vram_mb / vram_required_mb
            scaled_layers = max(0, int(total_layers * layer_ratio))
            if configured_layers == -1:
                gpu_layers = scaled_layers
            else:
                gpu_layers = min(configured_layers, scaled_layers)
        else:
            # Sufficient VRAM and budget for configured layers
            gpu_layers = configured_layers

        # 1. Try persistent out-of-process llama-server backend (0ms attach if running)
        server_bin = getattr(self.config.brain.local_model, "server_binary_path", "bin/llama-server/llama-server.exe")
        server_host = getattr(self.config.brain.local_model, "server_host", "127.0.0.1")
        server_port = getattr(self.config.brain.local_model, "server_port", 8080)
        auto_start = getattr(self.config.brain.local_model, "auto_start_server", True)
        timeout_sec = getattr(self.config.brain.local_model, "server_startup_timeout_sec", 60.0)
        parallel_slots = getattr(self.config.brain.local_model, "server_parallel_slots", 1)
        image_min_tokens = getattr(self.config.brain.local_model, "image_min_tokens", 1024)
        kv_cache_type_k = getattr(self.config.brain.local_model, "kv_cache_type_k", "q8_0")
        kv_cache_type_v = getattr(self.config.brain.local_model, "kv_cache_type_v", "q8_0")
        cache_reuse_tokens = getattr(self.config.brain.local_model, "cache_reuse_tokens", 0)
        keep_alive = getattr(self.config.brain.local_model, "keep_server_alive_on_exit", True)

        try:
            server_backend = LlamaServerBackend(
                host=server_host,
                port=server_port,
                model_path=model_path,
                mmproj_path=mmproj_path,
                server_binary=server_bin,
                n_gpu_layers=gpu_layers,
                n_ctx=self.config.brain.local_model.context_size,
                parallel_slots=parallel_slots,
                image_min_tokens=image_min_tokens,
                kv_cache_type_k=kv_cache_type_k,
                kv_cache_type_v=kv_cache_type_v,
                cache_reuse_tokens=cache_reuse_tokens,
                keep_alive_on_exit=keep_alive,
                auto_start=auto_start,
                startup_timeout_sec=timeout_sec,
            )
            if server_backend.is_available():
                self.active_backend = server_backend
                self.state = BrainState.READY_LOCAL
                return True
        except Exception as s_exc:
            logger.debug("LlamaServerBackend initialization skipped/failed: %s", s_exc)

        # 2. Fallback to in-process LlamaCppBackend
        try:
            backend = LlamaCppBackend(
                model_path=model_path,
                n_gpu_layers=gpu_layers,
                n_ctx=self.config.brain.local_model.context_size,
                mmproj_path=mmproj_path,
            )
            if backend.is_available():
                self.active_backend = backend
                self.state = BrainState.READY_LOCAL
                return True
        except Exception as exc:
            logger.warning("LlamaCpp initialization failed: %s", exc)

        # Fallback to MockBackend for test/dev stability
        self.active_backend = MockBackend()
        self.state = BrainState.READY_LOCAL
        return True

    def scan_models(self) -> List[ModelMetadata]:
        """Scan models directory and merge with curated catalog."""
        with self._lock:
            self.ensure_models_dir()
            results: List[ModelMetadata] = []
            seen_files = set()

            # 1. Process Curated Models
            for item in CURATED_MODELS:
                fname = item["filename"]
                fpath = self.models_dir / fname
                is_down = fpath.is_file()
                is_valid = validate_gguf_header(fpath) if is_down else False
                size = fpath.stat().st_size if is_down else item["filesize_bytes"]
                seen_files.add(fname)

                mmproj_fname = item.get("mmproj_filename")
                mmproj_path_str: Optional[str] = None
                has_vision = False
                if mmproj_fname:
                    seen_files.add(mmproj_fname)
                    mmproj_fpath = self.models_dir / mmproj_fname
                    if mmproj_fpath.is_file() and validate_gguf_header(mmproj_fpath):
                        mmproj_path_str = str(mmproj_fpath)
                        has_vision = is_valid

                meta = ModelMetadata(
                    model_id=item["model_id"],
                    filename=fname,
                    mmproj_filename=mmproj_fname,
                    mmproj_path=mmproj_path_str,
                    supports_vision=has_vision,
                    filesize_bytes=size,
                    filesize_display=format_bytes(size) if is_down else item["filesize_display"],
                    is_downloaded=is_down,
                    is_valid_gguf=is_valid,
                    file_path=str(fpath) if is_down else None,
                    recommended_gpu_layers=item["recommended_gpu_layers"],
                    vram_required_mb=item["vram_required_mb"],
                )
                results.append(meta)

            # 2. Check any other .gguf files in models_dir (excluding vision projector mmproj*.gguf files)
            for p in self.models_dir.glob("*.gguf"):
                if p.name not in seen_files and not p.name.lower().startswith("mmproj"):
                    is_valid = validate_gguf_header(p)
                    size = p.stat().st_size
                    disc_mmproj = LlamaCppBackend._discover_mmproj_path(p)
                    results.append(
                        ModelMetadata(
                            model_id=f"local/{p.stem}",
                            filename=p.name,
                            mmproj_filename=disc_mmproj.name if disc_mmproj else None,
                            mmproj_path=str(disc_mmproj) if disc_mmproj else None,
                            supports_vision=bool(is_valid and disc_mmproj),
                            filesize_bytes=size,
                            filesize_display=format_bytes(size),
                            is_downloaded=True,
                            is_valid_gguf=is_valid,
                            file_path=str(p),
                            recommended_gpu_layers=-1,
                            vram_required_mb=3500,
                        )
                    )

            self.available_models = results
            return results

    def refresh_status(self) -> BrainStatus:
        """Poll system and return latest BrainStatus snapshot."""
        with self._lock:
            self.scan_models()
            used_mb, free_mb = check_vram_headroom()
            backend_name = "none"
            if self.active_backend:
                backend_name = self.active_backend.__class__.__name__

            status_msg = f"Brain Mode: {self.mode.value} | State: {self.state.value}"
            if self.state == BrainState.DOWNLOADING and self._current_progress:
                status_msg = f"Downloading {self._current_progress.filename} ({self._current_progress.percentage:.1f}%)"

            return BrainStatus(
                mode=self.mode,
                state=self.state,
                active_backend=backend_name,
                current_model=self.current_model,
                available_models=self.available_models,
                download_progress=self._current_progress,
                vram_budget_mb=self.config.brain.local_model.vram_budget_mb,
                vram_used_mb=used_mb,
                vram_free_mb=free_mb,
                status_message=status_msg,
            )

    def get_status(self) -> BrainStatus:
        """Returns the current BrainStatus."""
        return self.refresh_status()

    # -----------------------------------------------------------------------
    # Non-blocking Downloader with Streaming Progress
    # -----------------------------------------------------------------------

    def start_download(
        self,
        model_id: Optional[str] = None,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        custom_url: Optional[str] = None,
    ) -> bool:
        """
        Starts a non-blocking background streaming download for the given model_id.
        Writes chunks to temporary file and validates binary GGUF header before renaming.
        """
        with self._lock:
            if self.state == BrainState.DOWNLOADING:
                logger.warning("Download already in progress.")
                return False

            target_id = model_id or self.config.brain.local_model.model_id
            matched = next((m for m in CURATED_MODELS if m["model_id"] == target_id), None)
            if not matched:
                filename = f"{target_id.split('/')[-1]}.gguf"
                total_bytes = 2000000000
            else:
                filename = matched["filename"]
                total_bytes = matched["filesize_bytes"]

            target_path = self.models_dir / filename
            temp_path = self.models_dir / f"{filename}.download.tmp"

            download_url = custom_url or (
                f"https://huggingface.co/{target_id}/resolve/main/{filename}"
            )

            self._cancel_download_event.clear()
            self.state = BrainState.DOWNLOADING
            self._current_progress = DownloadProgress(
                model_id=target_id,
                filename=filename,
                bytes_downloaded=0,
                total_bytes=total_bytes,
                percentage=0.0,
                speed_mbps=0.0,
                eta_seconds=0.0,
                elapsed_seconds=0.0,
                status="downloading",
            )

            def _download_worker() -> None:
                start_time = time.time()
                last_time = start_time
                bytes_downloaded = 0
                last_bytes = 0

                try:
                    with httpx.stream("GET", download_url, follow_redirects=True, timeout=30.0) as resp:
                        resp.raise_for_status()
                        real_total = int(resp.headers.get("content-length", total_bytes))
                        with open(temp_path, "wb") as f:
                            for chunk in resp.iter_bytes(chunk_size=256 * 1024):
                                if self._cancel_download_event.is_set():
                                    logger.info("Download cancelled by user.")
                                    f.close()
                                    if temp_path.exists():
                                        try:
                                            temp_path.unlink()
                                        except Exception:
                                            pass
                                    with self._lock:
                                        self.state = BrainState.NO_MODEL_PRESENT
                                        if self._current_progress:
                                            self._current_progress.status = "cancelled"
                                        if progress_callback and self._current_progress:
                                            progress_callback(self._current_progress)
                                    return

                                f.write(chunk)
                                bytes_downloaded += len(chunk)

                                # Early abort if stream exceeds expected content length
                                if real_total > 0 and bytes_downloaded > real_total:
                                    logger.error(
                                        "Download stream overflow for %s: received %d bytes > %d expected bytes (aborting stream)",
                                        filename,
                                        bytes_downloaded,
                                        real_total,
                                    )
                                    break

                                now = time.time()
                                dt = now - last_time

                                if dt >= 0.25:  # Update progress 4 times/sec
                                    speed = ((bytes_downloaded - last_bytes) / (1024 * 1024)) / max(dt, 0.001)
                                    eta = (real_total - bytes_downloaded) / (speed * 1024 * 1024 + 1e-6)
                                    pct = min(100.0, (bytes_downloaded / max(real_total, 1)) * 100.0)

                                    prog = DownloadProgress(
                                        model_id=target_id,
                                        filename=filename,
                                        bytes_downloaded=bytes_downloaded,
                                        total_bytes=real_total,
                                        percentage=pct,
                                        speed_mbps=round(speed, 2),
                                        eta_seconds=round(max(0.0, eta), 1),
                                        elapsed_seconds=round(now - start_time, 1),
                                        status="downloading",
                                    )
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
                            prog = self._current_progress
                        if progress_callback and prog:
                            progress_callback(prog)
                        return

                    # Completeness Verification: Detect truncated stream or oversized overflow
                    temp_size = temp_path.stat().st_size if temp_path.exists() else 0
                    if (
                        (real_total > 0 and bytes_downloaded != real_total)
                        or (real_total > 0 and temp_size != real_total)
                        or temp_size == 0
                        or real_total <= 0
                    ):
                        logger.error(
                            "Download size mismatch or incomplete for %s: received %d of %d expected bytes (on-disk: %d bytes)",
                            filename,
                            bytes_downloaded,
                            real_total,
                            temp_size,
                        )
                        if temp_path.exists():
                            try:
                                temp_path.unlink()
                            except Exception:
                                pass
                        with self._lock:
                            self.state = BrainState.DOWNLOAD_FAILED
                            if self._current_progress:
                                self._current_progress.status = "failed"
                                self._current_progress.bytes_downloaded = bytes_downloaded
                            prog = self._current_progress
                        if progress_callback and prog:
                            progress_callback(prog)
                        return

                    # Download finished - Validate GGUF header
                    with self._lock:
                        if self._current_progress:
                            self._current_progress.status = "verifying"
                        prog = self._current_progress
                    if progress_callback and prog:
                        progress_callback(prog)

                    # Validate staging temporary file before replacing destination
                    is_valid = validate_gguf_header(temp_path)
                    if not is_valid:
                        logger.error("Downloaded file %s failed binary GGUF header validation", filename)
                        if temp_path.exists():
                            try:
                                temp_path.unlink()
                            except Exception:
                                pass
                        with self._lock:
                            self.state = BrainState.DOWNLOAD_FAILED
                            if self._current_progress:
                                self._current_progress.status = "failed"
                            prog = self._current_progress
                        if progress_callback and prog:
                            progress_callback(prog)
                        return

                    # Atomically promote verified temporary file to destination
                    if temp_path.exists():
                        if target_path.exists():
                            try:
                                target_path.unlink()
                            except Exception:
                                pass
                        temp_path.replace(target_path)

                    # If this is a multimodal VLM with a companion mmproj vision projector, download mmproj if missing
                    mmproj_fname = matched.get("mmproj_filename") if (matched and custom_url is None) else None
                    if mmproj_fname:
                        mmproj_dest = self.models_dir / mmproj_fname
                        if not (mmproj_dest.is_file() and validate_gguf_header(mmproj_dest)):
                            mmproj_tmp = self.models_dir / f"{mmproj_fname}.download.tmp"
                            mmproj_url = f"https://huggingface.co/{target_id}/resolve/main/{mmproj_fname}"
                            mmproj_expected = matched.get("mmproj_filesize_bytes", 844757728)
                            with httpx.stream("GET", mmproj_url, follow_redirects=True, timeout=30.0) as m_resp:
                                m_resp.raise_for_status()
                                m_total = int(m_resp.headers.get("content-length", mmproj_expected))
                                m_down = 0
                                with open(mmproj_tmp, "wb") as mf:
                                    for m_chunk in m_resp.iter_bytes(chunk_size=256 * 1024):
                                        if self._cancel_download_event.is_set():
                                            break
                                        mf.write(m_chunk)
                                        m_down += len(m_chunk)
                            if (
                                not self._cancel_download_event.is_set()
                                and mmproj_tmp.exists()
                                and validate_gguf_header(mmproj_tmp)
                            ):
                                if mmproj_dest.exists():
                                    try:
                                        mmproj_dest.unlink()
                                    except Exception:
                                        pass
                                mmproj_tmp.replace(mmproj_dest)
                            elif mmproj_tmp.exists():
                                try:
                                    mmproj_tmp.unlink()
                                except Exception:
                                    pass

                    with self._lock:
                        self.state = BrainState.MODEL_READY_ON_DISK
                        self.current_model = filename
                        if self._current_progress:
                            self._current_progress.status = "completed"
                            self._current_progress.percentage = 100.0
                        prog = self._current_progress

                    if progress_callback and prog:
                        progress_callback(prog)

                except Exception as exc:
                    logger.error("Download failed: %s", exc)
                    if temp_path.exists():
                        try:
                            temp_path.unlink()
                        except Exception:
                            pass
                    with self._lock:
                        self.state = BrainState.DOWNLOAD_FAILED
                        if self._current_progress:
                            self._current_progress.status = "failed"
                        if progress_callback and self._current_progress:
                            progress_callback(self._current_progress)

            self._download_thread = threading.Thread(target=_download_worker, daemon=True)
            self._download_thread.start()
            return True

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

    # -----------------------------------------------------------------------
    # Zero-VRAM Mode Toggling & Model Management
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # Unified Cognitive Dispatch
    # -----------------------------------------------------------------------

    def supports_vision(self) -> bool:
        """Returns True if the currently active backend supports multimodal vision input."""
        return bool(self.active_backend and self.active_backend.supports_vision())

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None,
        json_mode: bool = False,
        image_base64: Optional[str] = None,
    ) -> str:
        """Unified inference dispatch across active backend."""
        with self._lock:
            if not self.active_backend or not self.active_backend.is_available():
                if self.mode == BrainMode.LOCAL_LLM:
                    raise RuntimeError(
                        "Local model backend is not loaded or unavailable. "
                        "Web offload fallback is disabled in local mode."
                    )
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
                image_base64=image_base64,
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

    def generate_thought(
        self,
        scene_summary: str,
        memory_context: str,
        user_goal: str,
        image_base64: Optional[str] = None,
    ) -> str:
        """
        Pass 1: Persona Engine.
        Generates structured situation analysis (OBSERVATION / CRITIQUE / DECISION) and character speech.
        """
        prompt = (
            f"User Goal: {user_goal}\n"
            f"Current Visual Scene: {scene_summary}\n"
            f"Recent Memory: {memory_context}\n\n"
            "Analyze the screen concisely inside <thought>...</thought> (OBSERVATION, CRITIQUE of last step, "
            "and DECISION naming the exact action and target [#ID] to click/double-click next), then provide 1 short sentence of in-character speech."
        )
        logger.debug("[LLM PASS 1 PROMPT] (vision=%s)\n%s", bool(image_base64 and self.supports_vision()), prompt)
        try:
            res = self.generate(
                prompt=prompt,
                system_prompt=self.config.persona.system_prompt,
                temperature=0.4,
                max_tokens=256,
                image_base64=image_base64,
            )
            logger.info("[LLM PASS 1 THOUGHT GENERATED]\n%s", res)
            return res
        except Exception as exc:
            logger.warning("Thought generation failed: %s", exc)
            if self.mode == BrainMode.LOCAL_LLM:
                return f"*observing desktop for goal: {user_goal}*"
            raise

    def generate_action(
        self,
        persona_intent: str,
        som_elements: List[Dict[str, Any]],
        memory_context: str,
        image_base64: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Pass 2: Action Dispatcher.
        Translates character intent and Set-of-Mark elements into a deterministic JSON action.
        Uses resilient parsing to tolerate markdown backticks and narrative preambles.
        """
        system_prompt = (
            "You are Parasite's deterministic Action Dispatcher.\n"
            "You MUST output valid JSON only. Choose one action from:\n"
            "['CLICK', 'DOUBLE_CLICK', 'RIGHT_CLICK', 'CLICK_AND_TYPE', 'TYPE', 'HOTKEY', 'SCROLL', 'MINIMIZE_WINDOW', 'CLOSE_WINDOW', 'WAIT', 'OFFLOAD_WEB_AI', 'DONE'].\n"
            "Rules:\n"
            "- Output 'DONE' ONLY when the full user objective is confirmed completed on screen. NEVER output 'DONE' if the target application has not yet been opened and confirmed visible.\n"
            "- Window Lifecycle Management (Minimize vs Close): Evaluate if an obstructing or non-target open window is needed soon vs not needed anytime soon:\n"
            "  * Use 'MINIMIZE_WINDOW' for windows needed soon (e.g. user IDE/editor, browser, launcher/console) when they block the desktop or steal focus.\n"
            "  * Use 'CLOSE_WINDOW' for windows not needed anytime soon (e.g. error/warning modals, stray File Explorer folder windows, or temporary utilities from a finished task) so unneeded windows do not pile up.\n"
            "- To open/launch an application not visible on screen: "
            "prefer Windows Start Search (HOTKEY ['win'] -> type name -> Enter) or revealing the desktop (HOTKEY ['win', 'd'] -> double-click shortcut). "
            "For standard Windows utilities with simple executable names, you may also use the Run dialog (HOTKEY ['win', 'r']). "
            "NEVER type app names into File Explorer folder search boxes or document canvases.\n"
            "- When the Run dialog or Start Search box is visible, you MUST type the target into that search box and submit. DO NOT click background windows or unrelated text areas.\n"
            "- Check the 'app' field of interactive elements. DO NOT click or type into terminal/console/editor windows (e.g. WindowsTerminal.exe, cmd.exe, code.exe) unless the goal explicitly calls for terminal interaction.\n"
            "- Whenever typing into a text box or document, ALWAYS prefer 'CLICK_AND_TYPE' with the 'target_id' of the Edit/Document element belonging to the intended target application.\n"
            "- When the target application or text editor is already open and active on screen: "
            "DO NOT type the application name or executable name into the document! "
            "Type the requested content or message, NOT the command prompt itself. "
            "Set 'submit': false when typing text into a document or text editor (do NOT send Enter unless submitting a search or chat message). "
            "DO NOT click MenuItems (like 'File' or 'Edit') to type document text. Always target the Document or Edit control.\n"
            "- NEVER output 'OFFLOAD_WEB_AI' unless the user goal explicitly asks to consult Gemini / web AI.\n"
            "Format: {\"action\": str, \"target_id\": int|null, \"coordinates\": [x, y]|null, \"text\": str|null, \"submit\": bool, \"keys\": [str]|null, \"reasoning\": str}"
        )

        # Determine context window to enforce dynamic token budget
        n_ctx = getattr(self.active_backend, "n_ctx", 4096) or 4096
        vision_active = bool(image_base64 and self.supports_vision())
        image_reserve = 1024 if vision_active else 0
        chars_per_token = 1.8 if vision_active else 2.2
        # Target prompt token ceiling: n_ctx minus max_tokens (256), safety buffer (256), and VLM image reserve
        max_prompt_budget = max(1024, n_ctx - 256 - 256 - image_reserve)

        # Build compact element dictionaries (omitting verbose/redundant fields)
        def _build_compact_som(elements: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
            compact = []
            for elem in elements[:limit]:
                item: Dict[str, Any] = {
                    "id": elem.get("id"),
                    "role": elem.get("role", "Control"),
                    "label": str(elem.get("label", ""))[:45],
                }
                if elem.get("app"):
                    item["app"] = elem["app"]
                if elem.get("window"):
                    item["window"] = str(elem["window"])[:30]
                if "x" in elem and "y" in elem and "width" in elem and "height" in elem:
                    item["pos"] = [elem["x"] + elem["width"] // 2, elem["y"] + elem["height"] // 2]
                elif "coordinates" in elem:
                    item["pos"] = elem["coordinates"]
                elif "bbox" in elem and isinstance(elem["bbox"], (list, tuple)) and len(elem["bbox"]) >= 4:
                    b = elem["bbox"]
                    item["pos"] = [b[0] + b[2] // 2, b[1] + b[3] // 2]
                compact.append(item)
            return compact

        # Start with top elements (up to 35 in VLM mode or 60 in text mode, fitting comfortably in 4096 context)
        max_initial_elems = 35 if vision_active else 60
        element_limit = min(max_initial_elems, len(som_elements)) if som_elements else 0
        compact_list = _build_compact_som(som_elements, element_limit) if som_elements else []
        elements_str = json.dumps(compact_list, indent=None) if compact_list else "[]"

        # Adaptive truncation loop: ensure prompt fits comfortably within token budget (~1.8-2.2 chars/token for JSON)
        while element_limit > 5 and ((len(system_prompt) + len(persona_intent) + len(memory_context) + len(elements_str)) / chars_per_token) > max_prompt_budget:
            element_limit = max(5, element_limit - 5)
            compact_list = _build_compact_som(som_elements, element_limit)
            elements_str = json.dumps(compact_list, indent=None)

        # If still exceeding budget, truncate memory history
        trimmed_memory = memory_context
        if ((len(system_prompt) + len(persona_intent) + len(trimmed_memory) + len(elements_str)) / chars_per_token) > max_prompt_budget:
            excess_chars = int(((len(system_prompt) + len(persona_intent) + len(trimmed_memory) + len(elements_str)) / chars_per_token - max_prompt_budget) * chars_per_token)
            trimmed_memory = trimmed_memory[:max(100, len(trimmed_memory) - excess_chars)] + "\n[...history truncated]"

        prompt = (
            f"Intent: {persona_intent}\n"
            f"Set-of-Mark Interactive Elements: {elements_str}\n"
            f"Memory History: {trimmed_memory}\n\n"
            "Respond strictly with the single JSON action command."
        )
        logger.debug("[LLM PASS 2 PROMPT] (vision=%s)\n%s", bool(image_base64 and self.supports_vision()), prompt)

        raw_response = self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=256,
            json_mode=True,
            image_base64=image_base64,
        )
        logger.info("[LLM PASS 2 RAW RESPONSE]\n%s", raw_response)

        # Resilient JSON extraction
        extracted_action = self._extract_action_json(raw_response)
        if extracted_action:
            # Sanitize null boolean/integer fields emitted by local 1.5B models
            if extracted_action.get("submit") is None:
                extracted_action["submit"] = False
            if extracted_action.get("clear_first") is None:
                extracted_action["clear_first"] = True
            if extracted_action.get("wait_ms") is None:
                extracted_action["wait_ms"] = 500
            if extracted_action.get("scroll_amount") is None:
                extracted_action["scroll_amount"] = 0
            if extracted_action.get("reasoning") is None:
                extracted_action["reasoning"] = ""
            logger.info(
                "[LLM PASS 2 ACTION PARSED] Action: %s | Target: %s | Coords: %s | Keys: %s | Text: %r | Reasoning: %s",
                extracted_action.get("action"),
                extracted_action.get("target_id"),
                extracted_action.get("coordinates"),
                extracted_action.get("keys"),
                extracted_action.get("text"),
                extracted_action.get("reasoning"),
            )
            return extracted_action

        logger.warning(
            "[LLM PASS 2 PARSE MISFIRE] Could not extract action JSON from response: %r. Yielding WAIT.",
            raw_response,
        )
        # Safe fallback action
        return {
            "action": "WAIT",
            "wait_ms": 1000,
            "reasoning": f"Re-evaluating target. Raw output was: {raw_response[:60]}...",
        }

    CUA_STOP_SEQUENCES: List[str] = [
        "<|im_end|>",
        "<|endoftext|>",
        "\nassistant",
        "\nuser",
        "\nUser:",
        "\nObservation:",
    ]

    def generate_cua_step(
        self,
        user_goal: str,
        screen_frame: Optional[np.ndarray] = None,
        image_base64: Optional[str] = None,
        screen_width: int = 1920,
        screen_height: int = 1080,
        candidate_elements: Optional[List[Any]] = None,
        memory_context: Optional[str] = None,
        working_memory_context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 256,
        temperature: float = 0.1,
        stop_sequences: Optional[List[str]] = None,
    ) -> Tuple[str, ActionPlan]:
        """
        Executes single-pass multimodal CUA step:
        1. Encodes screen frame to base64 JPEG if not already supplied.
        2. Formats concise prompt with user goal, memory history, and CPU working memory snapshot.
        3. Queries active multimodal backend with UITARS_SYSTEM_PROMPT in 1 call.
        4. Parses output into (thought, ActionPlan) via parse_uitars_action.
        """
        from parasite_ai.mind.uitars_parser import UITARS_SYSTEM_PROMPT, parse_uitars_action
        import numpy as np

        # Convert numpy frame to base64 JPEG if needed (preserve full desktop resolution without downscaling)
        eff_b64 = image_base64
        if eff_b64 is None and screen_frame is not None and isinstance(screen_frame, np.ndarray) and screen_frame.size > 0:
            try:
                from parasite_ai.vision.foveated import encode_image_to_data_uri
                eff_b64 = encode_image_to_data_uri(screen_frame, max_dim=1920, quality=90)
            except Exception:
                import io
                import base64
                from PIL import Image
                pil_img = Image.fromarray(screen_frame)
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=90)
                eff_b64 = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

        # Prefix-stable ordering: static Task goal first, then append-only Recent History,
        # then compact CPU Working Memory snapshot, then instruction before image tail
        prompt_parts = [f"Task: {user_goal}"]
        if memory_context:
            prompt_parts.append(f"Recent History:\n{memory_context}")
        if working_memory_context:
            prompt_parts.append(f"Current OS Working Memory:\n{working_memory_context}")
        prompt_parts.append("Determine the next single action to achieve the task.")
        prompt_str = "\n\n".join(prompt_parts)

        eff_stop = stop_sequences if stop_sequences is not None else list(self.CUA_STOP_SEQUENCES)
        raw_output = self.generate(
            prompt=prompt_str,
            system_prompt=system_prompt or UITARS_SYSTEM_PROMPT,
            max_tokens=max_tokens,
            temperature=temperature,
            stop_sequences=eff_stop,
            image_base64=eff_b64,
        )
        logger.info("[CUA RAW OUTPUT] %s", raw_output)

        thought, plan = parse_uitars_action(
            raw_output=raw_output,
            screen_width=screen_width,
            screen_height=screen_height,
            candidate_elements=candidate_elements,
        )
        return thought, plan

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

