#!/usr/bin/env python3
"""
GPU Governance and VRAM Headroom Verification Script.

Inspects physical GPU hardware via nvidia-smi, evaluates available VRAM headroom
against ParasiteAI's configured vram_budget_mb ceiling, checks WDDM sysmem fallback
risks, and outputs actionable telemetry for benchmark operators.
"""

import argparse
import json
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional


def query_nvidia_smi() -> Optional[Dict[str, Any]]:
    """Queries GPU metrics using nvidia-smi CLI."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None

    try:
        cmd = [
            exe,
            "--query-gpu=name,driver_version,memory.total,memory.free,memory.used",
            "--format=csv,noheader,nounits",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        if not lines:
            return None

        parts = [p.strip() for p in lines[0].split(",")]
        if len(parts) < 5:
            return None

        name = parts[0]
        driver_ver = parts[1]
        total_mb = int(float(parts[2]))
        free_mb = int(float(parts[3]))
        used_mb = int(float(parts[4]))

        return {
            "available": True,
            "gpu_name": name,
            "driver_version": driver_ver,
            "memory_total_mb": total_mb,
            "memory_free_mb": free_mb,
            "memory_used_mb": used_mb,
        }
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
        }


def check_gpu_governance(budget_mb: int = 6500) -> Dict[str, Any]:
    """Evaluates GPU governance health against model VRAM requirements."""
    info = query_nvidia_smi()
    if not info or not info.get("available"):
        return {
            "status": "FAIL",
            "message": "NVIDIA GPU or nvidia-smi not available.",
            "metrics": info or {},
            "recommendations": ["Ensure NVIDIA graphics drivers are installed and nvidia-smi is in PATH."],
        }

    total = info["memory_total_mb"]
    free = info["memory_free_mb"]
    used = info["memory_used_mb"]
    headroom_mb = free - budget_mb

    recommendations = []
    status = "PASS"

    if total < budget_mb:
        status = "FAIL"
        recommendations.append(
            f"Physical VRAM ({total} MB) is strictly smaller than the configured VRAM budget ({budget_mb} MB). "
            "Reduce vram_budget_mb in config.yaml or use a smaller quantization."
        )
    elif free < budget_mb:
        status = "WARN"
        recommendations.append(
            f"Currently only {free} MB VRAM is free ({used} MB used by desktop apps/displays). "
            f"Loading a {budget_mb} MB model will require {budget_mb - free} MB to be paged or freed. "
            "Under Windows WDDM, NVIDIA's Sysmem Fallback will spill excess tensors to system RAM across PCIe, "
            "which prevents CUDA OOM crashes but significantly reduces tokens/second."
        )
        recommendations.append(
            "Operator recommendation: Close GPU-heavy background applications before running local VLM benchmarks, "
            "or set 'CUDA - Sysmem Fallback Policy' to 'Prefer No Sysmem Fallback' in NVIDIA Control Panel to prevent PCIe paging."
        )
    else:
        recommendations.append(
            f"Sufficient VRAM headroom ({free} MB free >= {budget_mb} MB budget). "
            "VLM model can be fully offloaded into high-speed GDDR without triggering WDDM PCIe paging."
        )

    return {
        "status": status,
        "configured_budget_mb": budget_mb,
        "metrics": info,
        "headroom_mb": headroom_mb,
        "recommendations": recommendations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ParasiteAI GPU Governance & VRAM Headroom Inspector")
    parser.add_argument("--budget", type=int, default=6500, help="Target VRAM budget in MB (default: 6500)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON telemetry")
    args = parser.parse_args()

    report = check_gpu_governance(budget_mb=args.budget)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=" * 60)
        print(" ParasiteAI Hardware GPU Governance & VRAM Inspection")
        print("=" * 60)
        print(f"Status               : [{report['status']}]")
        print(f"Target Budget        : {report['configured_budget_mb']} MB")
        if "metrics" in report and report["metrics"].get("available"):
            m = report["metrics"]
            print(f"Device Name          : {m['gpu_name']}")
            print(f"Driver Version       : {m['driver_version']}")
            print(f"Total Dedicated VRAM : {m['memory_total_mb']} MB")
            print(f"Used VRAM (Desktop)  : {m['memory_used_mb']} MB")
            print(f"Free VRAM            : {m['memory_free_mb']} MB")
            print(f"Headroom vs Budget   : {report['headroom_mb']} MB")
        else:
            print(f"Error                : {report.get('message', 'No details')}")

        print("\nPolicy Assessment & Recommendations:")
        for rec in report.get("recommendations", []):
            print(f" - {rec}")
        print("=" * 60)

    return 0 if report["status"] in ("PASS", "WARN") else 1


if __name__ == "__main__":
    sys.exit(main())
