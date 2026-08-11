"""Explain a dashboard's resolved results in plain language.

Two engines, same contract as the chat builder (app/chat_build.py):

  * **Deterministic** — always available. Walks the resolved panels and writes
    one short paragraph per graph from the actual numbers: the headline value,
    the best and worst entries, the spread, and — for the DQ dimension boards —
    the operational lever that moves the dimension. No model, no network.
  * **LLM polish** — when a provider is configured, the deterministic notes and
    the raw numbers are handed to the model to rewrite as a analyst-style
    narrative. Any failure falls back to the deterministic text, so the button
    always answers.

The output is markdown: a `### <panel title>` block per panel, which the UI
renders under the dashboard.
"""
from __future__ import annotations

import json

from .panel_data import DQ_DIMENSIONS

# Query name -> the dimension it serves, for the lever line.
_DIM_BY_QUERY = {f"dq_{d.lower()}": d for d in DQ_DIMENSIONS}


def _fmt(v) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{v:,.1f}".rstrip("0").rstrip(".") if isinstance(v, float) else f"{v:,}"
    return str(v)


def _series_note(series: list[dict]) -> str:
    """Best / worst / spread, from a [{label, value}] series."""
    vals = [s for s in series if isinstance(s.get("value"), (int, float))]
    if not vals:
        return "No data points resolved for this panel."
    hi = max(vals, key=lambda s: s["value"])
    lo = min(vals, key=lambda s: s["value"])
    if hi is lo:
        return f"A single reading: **{hi['label']}** at {_fmt(hi['value'])}."
    note = (f"**{hi['label']}** leads at {_fmt(hi['value'])}; "
            f"**{lo['label']}** trails at {_fmt(lo['value'])}"
            f" — a spread of {_fmt(round(hi['value'] - lo['value'], 1))}.")
    if len(vals) > 2:
        mean = sum(s["value"] for s in vals) / len(vals)
        note += f" The average across {len(vals)} entries is {_fmt(round(mean, 1))}."
    return note


def _stacked_note(data: dict) -> str:
    cats = data.get("categories") or []
    groups = data.get("groups") or []
    if not cats or not groups:
        return "No data points resolved for this panel."
    totals = [sum(g.get("values", [0] * len(cats))[i] for g in groups) for i in range(len(cats))]
    first = groups[0]
    shares = [(_pct(first.get("values", [0] * len(cats))[i], totals[i]), cats[i])
              for i in range(len(cats)) if totals[i]]
    if not shares:
        return "No data points resolved for this panel."
    hi = max(shares)
    lo = min(shares)
    return (f"'{first.get('name')}' share is highest in **{hi[1]}** ({hi[0]}%) "
            f"and lowest in **{lo[1]}** ({lo[0]}%).")


def _pct(n, d) -> int:
    return round(100 * n / d) if d else 0


def _panel_note(panel: dict, data: dict) -> str:
    kind = data.get("kind") or panel.get("kind")
    query = panel.get("query", "")
    dim = _DIM_BY_QUERY.get(query)

    if data.get("error"):
        return f"Could not resolve this panel: {data['error']}."
    if kind == "kpi":
        unit = data.get("unit") or ""
        note = f"Reads **{_fmt(data.get('value', 0))}{unit}**."
        target = (panel.get("options") or {}).get("target")
        if isinstance(target, (int, float)) and isinstance(data.get("value"), (int, float)):
            gap = round(data["value"] - target, 1)
            note += (f" That is {_fmt(abs(gap))} {'above' if gap >= 0 else 'below'} "
                     f"the target of {_fmt(target)}.")
        return note
    if kind == "table":
        rows = data.get("rows") or []
        if not rows:
            return "The list is empty — nothing needs attention here right now."
        first = ", ".join(str(c) for c in rows[0][:3])
        return (f"{len(rows)} row(s) listed; the first is {first}. "
                f"Work the list top-down — it is ordered worst-first.")
    # chart
    if "groups" in data:
        note = _stacked_note(data)
    else:
        note = _series_note(data.get("series") or [])
    if dim:
        note += f" **{dim}** improves through {DQ_DIMENSIONS[dim][2]}."
    return note


def deterministic_explanation(spec: dict, resolved: dict) -> str:
    """One markdown block per panel, from the actual resolved numbers."""
    panels = resolved.get("panels") or {}
    scope = resolved.get("scope") or "all"
    head = [f"## {spec.get('title', 'Dashboard')} — what the numbers say"]
    if scope not in ("all", "All sources"):
        head.append(f"_Scoped to **{scope}**._")
    if resolved.get("demo"):
        head.append("_Resolved from the bundled sample catalog (demo data)._")
    out = ["\n".join(head)]
    for p in spec.get("panels", []):
        pid = p.get("id")
        data = panels.get(pid)
        if data is None or p.get("kind") == "text":
            continue
        out.append(f"### {p.get('title') or pid}\n{_panel_note(p, data)}")
    return "\n\n".join(out)


def _llm_rewrite(spec: dict, resolved: dict, notes: str) -> str | None:
    """Ask the configured model for an analyst-style narrative. None on any
    failure — the deterministic notes are always a complete answer."""
    from .llm import get_provider
    system = (
        "You are a data-governance analyst. Explain a dashboard's results to a "
        "colleague in plain language. One short paragraph per panel under a "
        "'### <panel title>' heading, in the panel order given. Name the actual "
        "numbers. Say what is good, what needs attention, and the single most "
        "useful next action. No preamble, no closing summary, markdown only."
    )
    user = (
        f"DASHBOARD: {spec.get('title')}\n"
        f"RESOLVED VALUES (JSON):\n{json.dumps(resolved.get('panels', {}))[:6000]}\n\n"
        f"DRAFT NOTES (correct numbers, dry tone — improve on these):\n{notes}"
    )
    try:
        # json_mode OFF: this is the one call that wants prose, and format=json
        # would force the local model to emit a JSON object instead.
        text = get_provider().complete(system, user, json_mode=False)
        return text.strip() or None
    except Exception:  # noqa: BLE001 — the deterministic notes always suffice
        return None


def explain_dashboard(spec: dict, resolved: dict) -> dict:
    """{markdown, engine} — LLM narrative when a provider answers, else the
    deterministic walk-through. Mirrors chat_build's offline-first contract."""
    notes = deterministic_explanation(spec, resolved)
    import os
    if os.getenv("LLM_PROVIDER", "local").lower() != "disabled":
        polished = _llm_rewrite(spec, resolved, notes)
        if polished:
            return {"markdown": polished, "engine": "llm"}
    return {"markdown": notes, "engine": "deterministic"}
