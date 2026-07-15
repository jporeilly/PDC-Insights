"""Hardware-aware LLM model recommendation.

Detects the host's OS, RAM, CPU cores, and any NVIDIA GPU, then recommends an
Ollama model tier. Shared by the CLI (tools/suggest_model.py) and the web app's
Settings page (GET /api/llm/suggest), so both give the same advice. Pure
standard library; detection never raises (degrades to conservative defaults).
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess

# (min GPU VRAM GB, model, why) — richest first. Tuned for reliable spec JSON.
GPU_TIERS = [
    (20, "qwen2.5:32b-instruct", "lots of VRAM — but 32B is overkill for spec JSON; 14B is plenty"),
    (9,  "qwen2.5:14b-instruct", "comfortable headroom for stronger chart-type choices"),
    (5,  "qwen2.5:7b-instruct",  "fast and strong at JSON — the recommended default"),
    (0,  "qwen2.5:3b-instruct",  "small GPU — a 3B keeps things responsive"),
]
# (min system RAM GB, model, why) — CPU is RAM-bound and slower, so prefer small.
CPU_TIERS = [
    (32, "qwen2.5:7b-instruct",   "plenty of RAM; 7B (Q4) runs on CPU, just slower than GPU"),
    (16, "qwen2.5:3b-instruct",   "3B is the sweet spot for CPU-only — usable latency"),
    (8,  "qwen2.5:1.5b-instruct", "limited RAM — a 1.5B keeps generation tractable"),
    (0,  "qwen2.5:0.5b-instruct", "very limited RAM — smallest model; expect weaker specs"),
]


def gpu_vram_gb() -> float | None:
    """Total NVIDIA VRAM in GB via nvidia-smi, or None if no NVIDIA GPU."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            text=True, timeout=10)
        return round(sum(int(x) for x in out.split()) / 1024, 1)  # sum across cards
    except Exception:  # noqa: BLE001 — detection must never crash
        return None


def ram_gb() -> float:
    """Total system RAM in GB, best-effort across platforms."""
    try:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3, 1)
    except (ValueError, OSError, AttributeError):
        pass
    if platform.system() == "Darwin":
        try:
            return round(int(subprocess.check_output(["sysctl", "-n", "hw.memsize"])) / 1024**3, 1)
        except Exception:  # noqa: BLE001
            pass
    if platform.system() == "Windows":
        try:
            out = subprocess.check_output(
                ["wmic", "ComputerSystem", "get", "TotalPhysicalMemory"], text=True)
            return round(int(out.split()[-1]) / 1024**3, 1)
        except Exception:  # noqa: BLE001
            pass
    return 0.0


def recommend(force_mode: str | None = None) -> dict:
    """Return {mode, model, why, ram_gb, vram_gb, cores, system}.

    Auto-detects GPU vs CPU by default. Pass force_mode='cpu' or 'gpu' (or set
    the INSIGHTS_FORCE_MODE env var) to override — the CPU/GPU toggle in the run
    scripts and Settings uses this so you can, e.g., pick a CPU-sized model even
    on a GPU box, or vice-versa.
    """
    cores = os.cpu_count() or 1
    ram = ram_gb()
    vram = gpu_vram_gb()
    forced = (force_mode or os.getenv("INSIGHTS_FORCE_MODE", "")).strip().lower()
    if forced in ("cpu", "gpu"):
        mode = forced
    else:
        mode = "gpu" if vram else "cpu"
    if mode == "gpu":
        # If forced to GPU without a detected card, assume a mid-range budget so
        # the suggestion is still reasonable rather than empty.
        budget = vram if vram else 8
        model, why = next((m, w) for thr, m, w in GPU_TIERS if budget >= thr)
    else:
        model, why = next((m, w) for thr, m, w in CPU_TIERS if ram >= thr)
    return {"mode": mode, "model": model, "why": why, "ram_gb": ram,
            "vram_gb": vram, "cores": cores, "system": platform.system()}
