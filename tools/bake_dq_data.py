"""Bake the DQ dimension boards' demo values for the React UI.

The UI ships offline "baked" renders of every standard dashboard
(frontend/src/data/dashboards.jsx); live values overlay them via
POST /api/dashboards/resolve. For the nine DQ dimension boards the baked
numbers are GENERATED from the same resolvers that answer /resolve in demo
mode, so the artwork and the overlay always agree — run this after changing
app/panel_data.py's dimension logic or the sample snapshot:

    python tools/bake_dq_data.py     # rewrites frontend/src/data/dqDemo.json
"""
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.catalog import SAMPLE_SNAPSHOT  # noqa: E402
from app.panel_data import DQ_DIMENSIONS, _dq_dim  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "frontend/src/data/dqDemo.json"


def main() -> None:
    boards = {}
    for dim, (offset, issue, lever) in DQ_DIMENSIONS.items():
        r = _dq_dim(dim)(SAMPLE_SNAPSHOT)
        boards[dim] = {
            "score": r["value"],
            "issue": issue,
            "lever": lever,
            "perSource": [{"k": s["label"], "v": s["value"]} for s in r["series"]],
            "fixRows": [row for row in r["rows"]],
        }
    OUT.write_text(json.dumps(boards, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name}: {len(boards)} dimensions")


if __name__ == "__main__":
    main()
