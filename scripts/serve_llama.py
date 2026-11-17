#!/usr/bin/env python3
"""
ParasiteAI - Persistent llama-server Supervisor & GPU Governance CLI.

Starts, stops, monitors, and pre-warms the local persistent llama-server daemon
with UI-TARS-1.5-7B (or Qwen2.5-VL), and enforces the 6,500 MB RTX 4060 VRAM budget.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import struct
import httpx

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from parasite_ai.config import AppConfig, load_config
from scripts.check_gpu_governance import check_gpu_governance, query_nvidia_smi

try:
    from parasite_ai.mind.brain_manager import CURATED_MODELS, validate_gguf_header
except ImportError:
    # Fallback if GUI / PyQt6 dependencies are not installed in calling python environment
    CURATED_MODELS = [
        {
            "model_id": "mradermacher/UI-TARS-1.5-7B-GGUF",
            "filename": "UI-TARS-1.5-7B.IQ4_XS.gguf",
            "mmproj_filename": "UI-TARS-1.5-7B.mmproj-Q8_0.gguf",
            "mmproj_filesize_bytes": 856130240,
            "filesize_bytes": 4250298688,
        }
    ]

    def validate_gguf_header(filepath: Any, min_bytes: int = 8) -> bool:
        path = Path(filepath)
        if not path.is_file() or path.stat().st_size < min_bytes:
            return False
        try:
            with open(path, "rb") as f:
                if f.read(4) != b"GGUF":
                    return False
                v = f.read(4)
                if len(v) < 4:
                    return False
                return struct.unpack("<I", v)[0] in (2, 3)
        except Exception:
            return False


def get_default_config() -> AppConfig:
    """Loads AppConfig from config.yaml or defaults."""
    cfg_path = WORKSPACE_ROOT / "config.yaml"
    if cfg_path.is_file():
        try:
            return load_config(cfg_path)
        except Exception:
            pass
    return AppConfig()


def resolve_executable(custom_path: Optional[str] = None) -> Optional[Path]:
    """Locates llama-server.exe."""
    candidates = []
    if custom_path:
        candidates.append(Path(custom_path))
        candidates.append(WORKSPACE_ROOT / custom_path)
    candidates.extend([
        WORKSPACE_ROOT / "bin" / "llama-server" / "llama-server.exe",
        WORKSPACE_ROOT / "bin" / "llama-server" / "llama.exe",
    ])
    for cand in candidates:
        if cand.is_file():
            return cand.resolve()
    which_path = shutil.which("llama-server") or shutil.which("llama-server.exe")
    if which_path:
        return Path(which_path)
    return None


def resolve_model_paths(
    model_override: Optional[str] = None,
    mmproj_override: Optional[str] = None,
) -> tuple[Optional[Path], Optional[Path]]:
    """Resolves model GGUF and companion mmproj projector."""
    cfg = get_default_config()
    models_dir = WORKSPACE_ROOT / cfg.system.models_dir

    model_path = None
    if model_override:
        model_path = Path(model_override)
        if not model_path.is_file():
            model_path = models_dir / model_override
    else:
        # Check configured model
        cfg_name = cfg.brain.local_model.filename
        cand = models_dir / cfg_name
        if cand.is_file():
            model_path = cand
        else:
            # Fallback search for any .gguf in models_dir (excluding mmproj)
            for p in sorted(models_dir.glob("*.gguf")):
                if not p.name.lower().startswith("mmproj") and not "mmproj" in p.name.lower():
                    model_path = p
                    break

    mmproj_path = None
    if mmproj_override:
        mmproj_path = Path(mmproj_override)
        if not mmproj_path.is_file():
            mmproj_path = models_dir / mmproj_override
    elif model_path:
        # Discover companion mmproj
        cfg_mmproj = cfg.brain.local_model.mmproj_filename
        if cfg_mmproj and (models_dir / cfg_mmproj).is_file():
            mmproj_path = models_dir / cfg_mmproj
        else:
            for p in sorted(models_dir.glob("*mmproj*.gguf")):
                mmproj_path = p
                break

    return model_path, mmproj_path


def check_health(host: str = "127.0.0.1", port: int = 8080) -> Dict[str, Any]:
    """Queries /health endpoint."""
    url = f"http://{host}:{port}/health"
    try:
        resp = httpx.get(url, timeout=2.0)
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


def status_cmd(args: argparse.Namespace) -> int:
    """Prints server health and GPU telemetry."""
    print("=" * 60)
    print(" ParasiteAI Persistent llama-server Supervisor Status")
    print("=" * 60)

    health = check_health(args.host, args.port)
    server_status = health.get("status", "unknown")
    print(f"Server Endpoint : http://{args.host}:{args.port}")
    print(f"Health Status   : [{server_status.upper()}]")
    if server_status != "ok":
        print(f"Diagnostic Info : {health}")

    print("\nGPU VRAM & Governance Telemetry:")
    gov = check_gpu_governance(budget_mb=args.budget_mb)
    metrics = gov.get("metrics", {})
    if metrics.get("available"):
        print(f"Device Name     : {metrics.get('gpu_name')}")
        print(f"Total VRAM      : {metrics.get('memory_total_mb')} MB")
        print(f"Used VRAM       : {metrics.get('memory_used_mb')} MB")
        print(f"Free VRAM       : {metrics.get('memory_free_mb')} MB")
        print(f"Governance State: [{gov.get('status')}]")
        for rec in gov.get("recommendations", []):
            print(f" - {rec}")
    else:
        print(f"GPU Info Unavailable: {gov.get('message')}")
    print("=" * 60)
    return 0 if server_status == "ok" else 1


def start_cmd(args: argparse.Namespace) -> int:
    """Starts llama-server daemon if not already running."""
    health = check_health(args.host, args.port)
    if health.get("status") == "ok":
        print(f"[+] llama-server is already running and ready at http://{args.host}:{args.port} (0ms cold start)")
        status_cmd(args)
        return 0

    exe = resolve_executable(args.binary)
    if not exe:
        print(f"[-] Error: Could not locate llama-server executable. Run `python scripts/provision_llama_server.py` first.")
        return 1

    model_path, mmproj_path = resolve_model_paths(args.model, args.mmproj)
    if not model_path or not model_path.is_file():
        print(f"[-] Error: Target model file not found ({model_path}). Place GGUF model in models/.")
        return 1

    print("=" * 60)
    print(" Launching Persistent llama-server Daemon")
    print("=" * 60)
    print(f"Executable      : {exe}")
    print(f"Model File      : {model_path} ({model_path.stat().st_size / (1024*1024):.1f} MB)")
    if mmproj_path and mmproj_path.is_file():
        print(f"Vision mmproj   : {mmproj_path} ({mmproj_path.stat().st_size / (1024*1024):.1f} MB)")
    else:
        print("Vision mmproj   : [NONE - Text Only]")
    cache_reuse_val = getattr(args, "cache_reuse", 0)
    is_multimodal = bool(mmproj_path and mmproj_path.is_file())
    if cache_reuse_val and cache_reuse_val > 0 and not is_multimodal:
        reuse_str = f" (cache-reuse={cache_reuse_val})"
    else:
        reuse_str = " (cache-reuse disabled)"
    print(f"Context Window  : {args.ctx_size} tokens")
    print(f"KV Cache Type   : K={args.cache_type_k}, V={args.cache_type_v}{reuse_str}")
    print(f"GPU Layers      : {args.ngl} (all offloaded)")
    print(f"Listen Address  : http://{args.host}:{args.port}")

    cmd = [
        str(exe),
        "-m", str(model_path.resolve()),
        "-c", str(args.ctx_size),
        "-ngl", str(args.ngl),
        "-np", str(args.parallel_slots),
        "--host", args.host,
        "--port", str(args.port),
        "-fa", "auto",
    ]
    if getattr(args, "cache_type_k", None):
        cmd.extend(["-ctk", str(args.cache_type_k)])
    if getattr(args, "cache_type_v", None):
        cmd.extend(["-ctv", str(args.cache_type_v)])
    if getattr(args, "cache_reuse", 0) and args.cache_reuse > 0 and not is_multimodal:
        cmd.extend(["--cache-reuse", str(args.cache_reuse)])
    if args.image_min_tokens and args.image_min_tokens > 0:
        cmd.extend(["--image-min-tokens", str(args.image_min_tokens)])
    if mmproj_path and mmproj_path.is_file():
        cmd.extend(["--mmproj", str(mmproj_path.resolve())])

    env = os.environ.copy()
    env["PATH"] = str(exe.parent) + os.pathsep + env.get("PATH", "")

    log_file = WORKSPACE_ROOT / "logs" / "llama_server.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    out_f = open(log_file, "a", encoding="utf-8") if args.daemon else None

    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
        if args.daemon:
            # DETACHED_PROCESS (0x8) and CREATE_BREAKAWAY_FROM_JOB (0x01000000)
            creation_flags |= 0x00000008
            creation_flags |= 0x01000000

    print("[*] Spawning server process...")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=out_f if args.daemon else None,
            stderr=out_f if args.daemon else None,
            env=env,
            creationflags=creation_flags,
        )
    except PermissionError:
        # Fallback if JobObject disallows breakaway
        creation_flags &= ~0x01000000
        proc = subprocess.Popen(
            cmd,
            stdout=out_f if args.daemon else None,
            stderr=out_f if args.daemon else None,
            env=env,
            creationflags=creation_flags,
        )

    print(f"[*] Process spawned (PID {proc.pid}). Waiting for /health readiness (timeout {args.timeout}s)...")
    start_t = time.time()
    while time.time() - start_t < args.timeout:
        if proc.poll() is not None:
            err = ""
            if proc.stderr:
                err = proc.stderr.read().decode("utf-8", errors="replace")
            print(f"[-] Server terminated prematurely (exit code {proc.returncode}):\n{err}")
            return 1

        h = check_health(args.host, args.port)
        if h.get("status") == "ok":
            elapsed = time.time() - start_t
            print(f"[+] Server ready at http://{args.host}:{args.port} in {elapsed:.2f}s!")
            status_cmd(args)
            if not args.daemon:
                print("[*] Running in foreground. Awaiting shutdown...")
                try:
                    return proc.wait()
                except KeyboardInterrupt:
                    proc.terminate()
                    return 0
            return 0
        time.sleep(0.5)

    print(f"[-] Startup timed out after {args.timeout}s.")
    return 1


def stop_cmd(args: argparse.Namespace) -> int:
    """Stops any running llama-server process."""
    print(f"[*] Stopping llama-server on port {args.port}...")
    killed = 0
    if os.name == "nt":
        # Check taskkill for llama-server.exe
        res = subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe", "/T"], capture_output=True, text=True)
        if "SUCCESS" in res.stdout:
            print("[+] Terminated llama-server.exe process(es).")
            killed += 1
        res2 = subprocess.run(["taskkill", "/F", "/IM", "llama.exe", "/T"], capture_output=True, text=True)
        if "SUCCESS" in res2.stdout:
            print("[+] Terminated llama.exe process(es).")
            killed += 1
    if killed == 0:
        print("[*] No active llama-server process was found.")
    return 0


def warm_cmd(args: argparse.Namespace) -> int:
    """Sends a quick inference request to pre-warm the model and measure latency."""
    print(f"[*] Pre-warming model at http://{args.host}:{args.port}...")
    health = check_health(args.host, args.port)
    if health.get("status") != "ok":
        print(f"[-] Server not ready: {health}")
        return 1

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "You are a desktop agent."},
    ]

    if getattr(args, "vision_smoke", False):
        import base64
        import io
        from PIL import Image

        buf = io.BytesIO()
        img = Image.new("RGB", (64, 64), color=(0, 128, 255))
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        print("[*] Running Multimodal Vision Smoke Test (synthetic 64x64 PNG)...")
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": "What color is this image? Reply in one word."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        })
    else:
        messages.append({
            "role": "user",
            "content": "Respond with 'READY' if operational.",
        })

    payload = {
        "model": "default",
        "messages": messages,
        "max_tokens": 32,
        "temperature": 0.1,
    }

    t0 = time.time()
    try:
        resp = httpx.post(f"http://{args.host}:{args.port}/v1/chat/completions", json=payload, timeout=args.timeout)
        resp.raise_for_status()
        latency = time.time() - t0
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        print(f"[+] Warmup inference successful in {latency:.3f}s!")
        print(f"    Response: {content}")
        return 0
    except Exception as exc:
        print(f"[-] Warmup failed: {exc}")
        return 1


def stream_download_file(url: str, dest_path: Path, expected_size: int = 0, max_retries: int = 10) -> bool:
    """Streams download with range resume, retry backoff, and verifies GGUF header."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.is_file() and validate_gguf_header(dest_path):
        current_size = dest_path.stat().st_size
        if expected_size == 0 or current_size == expected_size:
            print(f"[+] File already exists and passed GGUF validation: {dest_path.name} ({current_size / (1024*1024):.1f} MB)")
            return True

    tmp_path = dest_path.with_suffix(dest_path.suffix + ".download.tmp")
    timeout = httpx.Timeout(connect=30.0, read=180.0, write=60.0, pool=30.0)
    total_bytes = expected_size

    for attempt in range(1, max_retries + 1):
        existing_bytes = tmp_path.stat().st_size if tmp_path.exists() else 0
        headers = {}
        if existing_bytes > 0:
            headers["Range"] = f"bytes={existing_bytes}-"
            print(f"[*] Resuming download of {dest_path.name} from byte {existing_bytes} ({existing_bytes / (1024*1024):.1f} MB)... (Attempt {attempt}/{max_retries})")
        else:
            print(f"[*] Downloading {dest_path.name} from {url}... (Attempt {attempt}/{max_retries})")

        try:
            with httpx.Client(follow_redirects=True, timeout=timeout) as client:
                with client.stream("GET", url, headers=headers) as resp:
                    if resp.status_code == 416:
                        # Range Not Satisfiable - could mean file is already complete
                        if expected_size > 0 and existing_bytes == expected_size:
                            break
                        if tmp_path.exists():
                            tmp_path.unlink()
                        continue

                    resp.raise_for_status()

                    is_resume = (resp.status_code == 206)
                    if not is_resume and existing_bytes > 0:
                        existing_bytes = 0
                        file_mode = "wb"
                    else:
                        file_mode = "ab" if is_resume else "wb"

                    content_range = resp.headers.get("content-range")
                    if content_range and "/" in content_range:
                        try:
                            total_bytes = int(content_range.split("/")[-1])
                        except Exception:
                            total_bytes = expected_size
                    else:
                        cl = resp.headers.get("content-length")
                        if cl:
                            total_bytes = existing_bytes + int(cl)
                        else:
                            total_bytes = expected_size

                    bytes_done = existing_bytes
                    t_last = time.time()
                    chunk_size = 512 * 1024

                    with open(tmp_path, file_mode) as f:
                        for chunk in resp.iter_bytes(chunk_size=chunk_size):
                            f.write(chunk)
                            bytes_done += len(chunk)
                            now = time.time()
                            if now - t_last >= 1.0 or (total_bytes > 0 and bytes_done >= total_bytes):
                                pct = (bytes_done / total_bytes * 100.0) if total_bytes > 0 else 0.0
                                mb_done = bytes_done / (1024 * 1024)
                                mb_total = total_bytes / (1024 * 1024)
                                print(f"    Progress: {mb_done:.1f}/{mb_total:.1f} MB ({pct:.1f}%)", end="\r", flush=True)
                                t_last = now
                    print()

            current_tmp_size = tmp_path.stat().st_size if tmp_path.exists() else 0
            if total_bytes > 0 and current_tmp_size >= total_bytes:
                break
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            print(f"\n[!] Network interruption on attempt {attempt}: {exc}")
            if attempt < max_retries:
                time.sleep(2.0 * attempt)
            else:
                print(f"[-] Max retries reached for {dest_path.name}.")
                return False
        except Exception as exc:
            print(f"\n[-] Unexpected download error: {exc}")
            return False

    final_size = tmp_path.stat().st_size if tmp_path.exists() else 0
    if total_bytes > 0 and final_size != total_bytes:
        print(f"[-] Download truncated: got {final_size} bytes, expected {total_bytes} bytes.")
        return False

    print(f"[*] Validating GGUF header for {dest_path.name}...")
    if not validate_gguf_header(tmp_path):
        print(f"[-] GGUF header validation failed for {dest_path.name}!")
        if tmp_path.exists():
            tmp_path.unlink()
        return False

    if dest_path.exists():
        dest_path.unlink()
    tmp_path.rename(dest_path)
    print(f"[+] Successfully downloaded and verified: {dest_path.name} ({dest_path.stat().st_size / (1024*1024):.1f} MB)")
    return True


def download_cmd(args: argparse.Namespace) -> int:
    """Downloads model and mmproj weights into models directory."""
    cfg = get_default_config()
    models_dir = WORKSPACE_ROOT / cfg.system.models_dir
    models_dir.mkdir(parents=True, exist_ok=True)

    # Find model metadata from CURATED_MODELS or args
    target_filename = args.model or cfg.brain.local_model.filename
    target_meta = next((m for m in CURATED_MODELS if m.get("filename") == target_filename), None)
    if not target_meta:
        target_meta = CURATED_MODELS[0]

    model_id = args.model_id or target_meta.get("model_id", "mradermacher/UI-TARS-1.5-7B-GGUF")
    filename = target_meta.get("filename", "UI-TARS-1.5-7B.IQ4_XS.gguf")
    filesize = target_meta.get("filesize_bytes", 4250298688)
    mmproj_fname = target_meta.get("mmproj_filename", "UI-TARS-1.5-7B.mmproj-Q8_0.gguf")
    mmproj_size = target_meta.get("mmproj_filesize_bytes", 856130240)

    print("=" * 60)
    print(" ParasiteAI Model Provisioning")
    print(f" Target Repository : {model_id}")
    print(f" Model GGUF        : {filename} (~{filesize / (1024*1024):.1f} MB)")
    if mmproj_fname:
        print(f" Vision mmproj     : {mmproj_fname} (~{mmproj_size / (1024*1024):.1f} MB)")
    print(f" Destination Dir   : {models_dir}")
    print("=" * 60)

    model_url = f"https://huggingface.co/{model_id}/resolve/main/{filename}"
    dest_path = models_dir / filename
    ok = stream_download_file(model_url, dest_path, expected_size=filesize)
    if not ok:
        return 1

    if mmproj_fname:
        mmproj_url = f"https://huggingface.co/{model_id}/resolve/main/{mmproj_fname}"
        mmproj_dest = models_dir / mmproj_fname
        ok_mm = stream_download_file(mmproj_url, mmproj_dest, expected_size=mmproj_size)
        if not ok_mm:
            return 1

    print("\n[+] All required model weights are downloaded and verified on disk!")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ParasiteAI llama-server Supervisor CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Check llama-server health and GPU VRAM governance")
    p_status.add_argument("--host", default="127.0.0.1")
    p_status.add_argument("--port", type=int, default=8080)
    p_status.add_argument("--budget-mb", type=int, default=6500)
    p_status.set_defaults(func=status_cmd)

    # start
    p_start = subparsers.add_parser("start", help="Start persistent llama-server daemon")
    p_start.add_argument("--host", default="127.0.0.1")
    p_start.add_argument("--port", type=int, default=8080)
    p_start.add_argument("--binary", default=None)
    p_start.add_argument("--model", default=None)
    p_start.add_argument("--mmproj", default=None)
    p_start.add_argument("--ctx-size", type=int, default=8192)
    p_start.add_argument("--ngl", type=int, default=-1)
    p_start.add_argument("-np", "--parallel-slots", type=int, default=1, help="Number of parallel request slots (1 locks KV cache to single slot to conserve VRAM)")
    p_start.add_argument("--image-min-tokens", type=int, default=1024, help="Min vision tokens for desktop UI coordinate grounding (1024)")
    p_start.add_argument("-ctk", "--cache-type-k", default="q8_0", help="KV cache data type for K (default: q8_0)")
    p_start.add_argument("-ctv", "--cache-type-v", default="q8_0", help="KV cache data type for V (default: q8_0)")
    p_start.add_argument("--cache-reuse", type=int, default=0, help="Min chunk size to reuse from KV cache via KV shifting (default: 0, disabled for multimodal models)")
    p_start.add_argument("--timeout", type=float, default=60.0)
    p_start.add_argument("--budget-mb", type=int, default=6500)
    p_start.add_argument("--daemon", action=argparse.BooleanOptionalAction, default=True, help="Run as background detached daemon (use --no-daemon for foreground/runner)")
    p_start.set_defaults(func=start_cmd)

    # stop
    p_stop = subparsers.add_parser("stop", help="Stop running llama-server daemon")
    p_stop.add_argument("--port", type=int, default=8080)
    p_stop.set_defaults(func=stop_cmd)

    # warm
    p_warm = subparsers.add_parser("warm", help="Pre-warm model with test prompt")
    p_warm.add_argument("--host", default="127.0.0.1")
    p_warm.add_argument("--port", type=int, default=8080)
    p_warm.add_argument("--vision-smoke", action="store_true", help="Run multimodal vision perception test with synthetic PNG")
    p_warm.add_argument("--timeout", type=float, default=60.0, help="Inference timeout in seconds")
    p_warm.set_defaults(func=warm_cmd)

    # download
    p_dl = subparsers.add_parser("download", help="Download UI-TARS model weights and mmproj from HuggingFace")
    p_dl.add_argument("--model-id", default=None, help="HuggingFace model ID (default from config/curated)")
    p_dl.add_argument("--model", default=None, help="Specific GGUF filename (e.g. UI-TARS-1.5-7B.IQ4_XS.gguf)")
    p_dl.set_defaults(func=download_cmd)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
