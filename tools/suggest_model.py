"""Suggest an Ollama model + run command based on this machine's hardware.

Thin CLI over app.model_advice.recommend() (shared with the Settings page's
/api/llm/suggest), plus the platform-appropriate native run command.

Run:  python tools/suggest_model.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.model_advice import recommend  # noqa: E402


def main() -> None:
    r = recommend()
    hw = f"{r['system']} · {r['cores']} cores · {r['ram_gb']} GB RAM"
    hw += f" · GPU {r['vram_gb']} GB VRAM" if r["vram_gb"] else " · no NVIDIA GPU"
    run = ("waitress-serve --port=8660 wsgi:app   # pip install waitress"
           if r["system"] == "Windows"
           else "gunicorn --bind 0.0.0.0:8660 --threads 4 wsgi:app")
    print(f"\nDetected: {hw}\nMode:     {r['mode'].upper()}")
    print(f"\nRecommended model:\n  ollama pull {r['model']}\n  ({r['why']})")
    print(f"\nSet in .env:\n  LLM_PROVIDER=local\n  LLM_MODEL={r['model']}")
    print("  LLM_BASE_URL=http://localhost:11434   # native Ollama on this host")
    if r["mode"] == "cpu":
        print("\nCPU tip: set OLLAMA_NUM_PARALLEL=1, expect slower generation than GPU, "
              "keep LLM_JSON_MODE=true.")
    print(f"\nRun the web app natively:\n  {run}\n")


if __name__ == "__main__":
    main()
