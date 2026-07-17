# Deployment & topology

> **Quick start:** `./run.sh` (macOS/Linux) or `run.bat` (Windows) creates the venv, installs deps, auto-detects GPU/CPU, and starts the app — add `--mcp` for the MCP server. The local LLM does not require the MCP server. The notes below cover the production/co-location trade-offs the script doesn't decide for you.

Catalog Insights is a **thin, stateless client**. It holds no data of its own —
it reads the PDC API on demand and (optionally) calls an LLM endpoint. That
makes placement flexible: it runs anywhere that can reach two endpoints, the
PDC API and the LLM.

```
        ┌──────────────────────────┐        ┌─────────────────────┐
        │  Catalog Insights        │  REST  │  PDC (Linux,        │
        │  FastAPI + uvicorn       │───────▶│  Docker containers) │
        │  (1 small container)     │        │  OpenSearch + svcs  │
        └─────────────┬────────────┘        └─────────────────────┘
                      │ HTTP
                      ▼
        ┌──────────────────────────┐
        │  LLM endpoint            │
        │  Ollama (local GPU) or   │
        │  a commercial API        │
        └──────────────────────────┘
```

## No Pentaho Server, CTools, or Semantic Model Editor

None of those are in the runtime path. The app talks to the **PDC public REST
API** and renders charts in the browser. There is no Pentaho Server, no
Mondrian/OLAP, no CDA, no CTools, and no Semantic Model Editor involved in
serving a dashboard.

The only place CTools appears anywhere in this project is the **optional**
export bridge in `PDC-CONNECTOR.md` — a path for teams whose delivery standard
*requires* a CDF/CDE artifact. It is entirely opt-in and plays no part in
running Catalog Insights. For your enablement goal (a standalone, low-friction
reporting tool) you can ignore it.

## Should it sit on the same server as PDC?

It can. PDC already ships as a set of Docker containers (managed via Portainer
in the lab), so adding one small Insights container to that host is
straightforward — and it means the app reaches the PDC API over localhost (no
extra firewall rules, lowest latency).

The caveat is headroom. The PDC family is resource-hungry — the documented
hardware sizing runs to **16–32 CPU cores and 64–128 GB RAM** — and you don't
want the reporting app competing with profiling/scan workloads. Guidance:

- **Lab / enablement:** co-locate. It's convenient and the footprint is tiny
  (a Python web process). Add it to the same compose/Portainer stack.
- **Production:** give it its own small VM or container on the **same network
  segment** as PDC. Same low-latency API calls, but it can't starve PDC, and
  you can restart/upgrade it independently.

Either way the app is stateless, so there's nothing to back up and scaling is
just "run another container."

### "MCP server on the same box as PDC?"

Same answer, and it's worth separating two things:

- **This app** is a REST client to PDC. Co-location rules above apply.
- **A reporting MCP server** (the alternative build path) would *also* be a
  thin client to the same PDC API — it just exposes the data to an LLM/agent
  instead of a browser. Its placement considerations are identical: fine to
  co-locate in a lab, prefer a small adjacent host in production. If you build
  both later, they can share the one PDC-connector layer and live side by side.

So: co-locating the MCP server (or this app) with PDC is reasonable, mainly for
the localhost API hop — just mind PDC's resource appetite in production.

## Running on your Windows 11 host (2× RTX 3060)

Yes — and your box is a good fit, because the GPUs make a **local** LLM
practical, which is the right default for governance metadata. Recommended split:

1. **Run Ollama natively on Windows.** The Windows installer uses CUDA and will
   use **both** 3060s automatically, splitting model layers across them. No
   Docker GPU plumbing needed.
2. **Run Catalog Insights natively too (recommended).** Since Ollama is already
   on the host, running the app directly on the host is the simplest, most
   flexible setup — `LLM_BASE_URL=http://localhost:11434` (the default) just
   works, with no container hop or `host.docker.internal` indirection:
   ```bash
   pip install -r requirements.txt
   uvicorn asgi:app --host 0.0.0.0 --port 5002
   ```
   Prefer a self-contained container instead? `docker compose up` works too — the
   compose file injects `host.docker.internal` so the containerised app still
   reaches the host's Ollama without any config change. Either path is supported;
   native is the lower-friction one when the model is on the same box.
3. **Point `PDC_BASE_URL` at your PDC instance over the network.** PDC itself
   runs on Linux; it does not need to be on the Windows box. The Windows host
   runs the app + the local model and talks to PDC remotely with a read-only
   account (e.g. `pdc_user`).

### Model sizing for 2× RTX 3060

A 3060 is typically a 12 GB card, so you have ~24 GB aggregate (not unified —
Ollama splits layers across the two). For generating a JSON dashboard spec you
don't need a large model:

| Model | Approx VRAM (Q4) | Fits | Note |
| ----- | ---------------- | ---- | ---- |
| `qwen2.5:7b-instruct` (default) | ~5 GB | one card | fast, strong JSON |
| `qwen2.5:14b-instruct` | ~9 GB | one card | more headroom |
| `qwen2.5:32b-instruct` | ~20 GB | both cards | slower; overkill here |

### No GPU? CPU works too

A GPU isn't required — generation also runs on CPU, just slower. Pick a smaller model (e.g. `qwen2.5:3b-instruct`, or `1.5b` on tight RAM), keep `LLM_JSON_MODE=true`, and optionally set `OLLAMA_NUM_PARALLEL=1`. Run `python tools/suggest_model.py` and it inspects the OS, RAM, cores, and any NVIDIA GPU to recommend a model and the native run command (uvicorn, same on every platform). Everything except generation latency is identical to the GPU path.

Keep `LLM_JSON_MODE=true` so Ollama constrains output to valid JSON — that
matters more than raw model size for this task. Start with 7B; step up to 14B
only if you see weak chart-type choices.

### If you'd rather containerise the model too

Run Ollama in its own container with GPU passthrough (Docker Desktop → WSL2
backend + NVIDIA Container Toolkit), then point `LLM_BASE_URL` at that service
name. It works, but native-Ollama-on-host is the lower-friction path and avoids
WSL GPU setup.
