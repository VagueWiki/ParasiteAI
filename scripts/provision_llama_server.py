#!/usr/bin/env python3
"""
ParasiteAI - llama-server Windows CUDA 12 Binary Provisioner.

Downloads official prebuilt llama.cpp Windows CUDA 12 binaries and runtime DLLs
from ggml-org/llama.cpp GitHub releases, extracts them to bin/llama-server/,
and verifies executable health.
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

REPO_API = "https://api.github.com/repos/ggml-org/llama.cpp/releases"
DEFAULT_TAG = "b12188"
TARGET_DIR = Path("bin/llama-server")


def find_release_assets(tag: Optional[str] = None) -> Tuple[str, Dict[str, str]]:
    """Locates the Windows CUDA 12 binary zip and cudart runtime zip for the target tag."""
    client = httpx.Client(timeout=30.0, follow_redirects=True)
    url = f"{REPO_API}/tags/{tag}" if tag else f"{REPO_API}?per_page=5"

    try:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch llama.cpp releases from GitHub: {exc}")

    release = data if tag else data[0]
    actual_tag = release.get("tag_name", "unknown")
    assets = release.get("assets", [])

    bin_url = None
    cudart_url = None

    for asset in assets:
        name = asset.get("name", "")
        dl_url = asset.get("browser_download_url", "")
        # Match CUDA 12.4 x64 windows binaries
        if "win-cuda-12.4-x64.zip" in name or "win-cuda-cu12" in name:
            if name.startswith("cudart-"):
                cudart_url = dl_url
            elif name.startswith("llama-"):
                bin_url = dl_url

    if not bin_url:
        # Fallback to any win-cuda-12 x64 binary
        for asset in assets:
            name = asset.get("name", "")
            dl_url = asset.get("browser_download_url", "")
            if "win-cuda-12" in name and name.endswith(".zip"):
                if "cudart" in name:
                    cudart_url = cudart_url or dl_url
                else:
                    bin_url = bin_url or dl_url

    if not bin_url:
        raise RuntimeError(f"Could not find Windows CUDA 12 binary zip in release {actual_tag}")

    downloads = {"bin": bin_url}
    if cudart_url:
        downloads["cudart"] = cudart_url

    return actual_tag, downloads


def download_file(url: str, dest_path: Path) -> Path:
    """Downloads a file with streaming progress."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(".tmp")

    print(f"[*] Downloading {dest_path.name} from {url}...")
    with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(temp_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = (downloaded / total) * 100.0
                    print(f"\r    {downloaded / (1024*1024):.1f} / {total / (1024*1024):.1f} MB ({pct:.1f}%)", end="", flush=True)
                else:
                    print(f"\r    {downloaded / (1024*1024):.1f} MB", end="", flush=True)
    print()

    if temp_path.exists():
        if dest_path.exists():
            dest_path.unlink()
        temp_path.rename(dest_path)
    return dest_path


def extract_zip(zip_path: Path, target_dir: Path) -> None:
    """Extracts zip archive into target directory, overwriting existing files."""
    print(f"[*] Extracting {zip_path.name} to {target_dir}...")
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(target_dir)


def verify_executable(target_dir: Path) -> bool:
    """Verifies that llama-server.exe exists and can run --version."""
    server_exe = target_dir / "llama-server.exe"
    if not server_exe.is_file():
        # Some recent builds name the unified executable llama.exe
        alt_exe = target_dir / "llama.exe"
        if alt_exe.is_file():
            print(f"[+] Found unified {alt_exe.name}; creating llama-server.exe alias/symlink.")
            try:
                shutil.copy2(alt_exe, server_exe)
            except Exception as copy_err:
                print(f"[!] Warning: Could not copy {alt_exe.name} to {server_exe.name}: {copy_err}")
                server_exe = alt_exe
        else:
            print(f"[-] Neither llama-server.exe nor llama.exe found in {target_dir}")
            return False

    print(f"[*] Verifying executable: {server_exe}...")
    try:
        env = os.environ.copy()
        env["PATH"] = str(target_dir.resolve()) + os.pathsep + env.get("PATH", "")
        res = subprocess.run([str(server_exe), "--version"], capture_output=True, text=True, timeout=10, env=env)
        print(f"[+] llama-server output (returncode={res.returncode}):\n{res.stdout.strip() or res.stderr.strip()}")
        return res.returncode == 0 or "version" in (res.stdout + res.stderr).lower()
    except Exception as exc:
        print(f"[-] Execution check failed: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision llama-server Windows CUDA 12 binaries.")
    parser.add_argument("--tag", default=DEFAULT_TAG, help=f"GitHub release tag (default: {DEFAULT_TAG})")
    parser.add_argument("--target-dir", default=str(TARGET_DIR), help="Destination directory for binaries")
    parser.add_argument("--check", action="store_true", help="Only check if executable is already provisioned and functional")
    args = parser.parse_args()

    dest_dir = Path(args.target_dir)

    if args.check:
        if (dest_dir / "llama-server.exe").is_file():
            ok = verify_executable(dest_dir)
            if ok:
                print("[+] llama-server is provisioned and operational.")
                return 0
        print("[-] llama-server is not provisioned or failed check.")
        return 1

    cache_dir = Path("models/.cache/llama-server")
    cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Locating llama.cpp release assets for tag '{args.tag}'...")
    actual_tag, downloads = find_release_assets(args.tag)
    print(f"[+] Resolved release tag: {actual_tag}")

    # 1. Download and extract cudart first if present
    if "cudart" in downloads:
        cudart_zip = cache_dir / f"cudart-{actual_tag}.zip"
        if not cudart_zip.is_file() or cudart_zip.stat().st_size < 1024:
            download_file(downloads["cudart"], cudart_zip)
        extract_zip(cudart_zip, dest_dir)

    # 2. Download and extract main binaries
    bin_zip = cache_dir / f"llama-{actual_tag}.zip"
    if not bin_zip.is_file() or bin_zip.stat().st_size < 1024:
        download_file(downloads["bin"], bin_zip)
    extract_zip(bin_zip, dest_dir)

    # 3. Verify executable health
    if verify_executable(dest_dir):
        print(f"\n[SUCCESS] llama-server Windows CUDA 12 successfully provisioned in {dest_dir.resolve()}")
        return 0
    else:
        print(f"\n[FAILURE] Failed to verify llama-server execution in {dest_dir.resolve()}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
