#!/usr/bin/env bash
# run.sh — launch Catalog Insights (web app, optionally the MCP server) with
#          preflight checks, hardware detection, and a post-start health report.
#
#   ./run.sh                 web app only (all you need for local LLM)
#   ./run.sh --mcp           also start the MCP server (for Claude Desktop / agents)
#   ./run.sh --gpu | --cpu   force model sizing (default: auto-detect via nvidia-smi)
#   ./run.sh --pull          download the recommended Ollama model
#   ./run.sh --port 9000     web app port (default 5002)
#   ./run.sh --no-venv       use the current Python instead of a .venv
#
# The local LLM (Ollama) is called directly by the web app — you do NOT need the
# MCP server for it. Use --mcp only for an external chat/agent like Claude Desktop.
set -euo pipefail
cd "$(dirname "$0")"

if [ -t 1 ]; then
  B=$'\e[1m'; DIM=$'\e[2m'; R=$'\e[0m'; GRN=$'\e[32m'; YEL=$'\e[33m'; RED=$'\e[31m'; CYN=$'\e[36m'
else B=""; DIM=""; R=""; GRN=""; YEL=""; RED=""; CYN=""; fi
ok(){   printf "  ${GRN}OK${R} %s\n" "$1"; }
warn(){ printf "  ${YEL} !${R} %s\n" "$1"; }
bad(){  printf "  ${RED} x${R} %s\n" "$1"; }
step(){ printf "\n${B}${CYN}%s${R}\n" "$1"; }

PORT=5002; WITH_MCP=0; FORCE=""; PULL=0; USE_VENV=1
while [ $# -gt 0 ]; do
  case "$1" in
    --mcp) WITH_MCP=1;; --gpu) FORCE=gpu;; --cpu) FORCE=cpu;; --pull) PULL=1;;
    --no-venv) USE_VENV=0;; --port) PORT="${2:?--port needs a number}"; shift;;
    -h|--help) sed -n '2,14p' "$0"; exit 0;;
    *) bad "unknown option: $1 (try --help)"; exit 1;;
  esac; shift
done

PY=python3; command -v python3 >/dev/null 2>&1 || PY=python
env_val(){ grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- || true; }
port_free(){ "$PY" tools/preflight.py port "$1"; }
http_ok(){ "$PY" tools/preflight.py http "$1"; }
hjson(){ "$PY" tools/preflight.py json "$1" "$2" 2>/dev/null || true; }

printf "${B}Catalog Insights${R} ${DIM}launcher${R}\n"

step "Preflight"
"$PY" -c 'import sys; raise SystemExit(0 if sys.version_info>=(3,9) else 1)' \
  && ok "Python $("$PY" -V 2>&1 | awk '{print $2}')" \
  || { bad "Python 3.9+ required"; exit 1; }

if [ "$USE_VENV" = 1 ]; then
  [ -d .venv ] || { warn "creating .venv…"; "$PY" -m venv .venv; }
  # shellcheck disable=SC1091
  source .venv/bin/activate; ok "virtualenv active (.venv)"
else warn "using current Python (--no-venv)"; fi

printf "  ${DIM}installing dependencies…${R}\n"
pip install -q -r requirements.txt && ok "web app dependencies installed"
[ "$WITH_MCP" = 1 ] && pip install -q -r requirements-mcp.txt && ok "MCP dependencies installed"

if [ ! -f .env ]; then cp .env.example .env; warn ".env created from .env.example — edit for PDC/LLM, or set INSIGHTS_DEMO=true"; else ok ".env present"; fi
[ "$(port_free "$PORT")" = busy ] && { bad "port $PORT is in use — pass --port N"; exit 1; } || ok "port $PORT is free"

step "Hardware & model"
MODE="$FORCE"
if [ -z "$MODE" ]; then
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then MODE=gpu; else MODE=cpu; fi
fi
export INSIGHTS_FORCE_MODE="$MODE"
[ "$MODE" = cpu ] && export OLLAMA_NUM_PARALLEL=1
[ "$MODE" = gpu ] && ok "GPU detected -> GPU model sizing" || ok "no GPU -> CPU model sizing (OLLAMA_NUM_PARALLEL=1)"

REC="$("$PY" -c "from app.model_advice import recommend; print(recommend('$MODE')['model'])" 2>/dev/null || true)"
[ -n "$REC" ] && printf "  ${DIM}recommended model:${R} %s\n" "$REC"

PROVIDER="$(env_val LLM_PROVIDER)"; PROVIDER="${PROVIDER:-local}"
LLM_URL="$(env_val LLM_BASE_URL)"; LLM_URL="${LLM_URL:-http://localhost:11434}"
if [ "$PROVIDER" = local ]; then
  [ "$(http_ok "$LLM_URL/api/tags")" = ok ] && ok "Ollama reachable at $LLM_URL" \
    || warn "Ollama not reachable at $LLM_URL — /chat uses the offline builder until it's up"
  if [ "$PULL" = 1 ] && [ -n "$REC" ]; then
    if command -v ollama >/dev/null 2>&1; then printf "  ${DIM}pulling %s…${R}\n" "$REC"; ollama pull "$REC" || true
    else warn "ollama not on PATH — skipping --pull (use Settings -> Download model)"; fi
  fi
else ok "LLM provider: $PROVIDER (no local Ollama needed)"; fi

step "Starting"
LOG="$(mktemp)"; SRV_PID=""; MCP_PID=""
cleanup(){ [ -n "$MCP_PID" ] && kill "$MCP_PID" 2>/dev/null || true
           [ -n "$SRV_PID" ] && kill "$SRV_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

if [ "$WITH_MCP" = 1 ]; then
  MCP_HTTP=1 "$PY" -m mcp_server.server >/dev/null 2>&1 & MCP_PID=$!
  ok "MCP server starting on :8765 (pid $MCP_PID)"
fi

if command -v gunicorn >/dev/null 2>&1; then
  gunicorn --bind "0.0.0.0:$PORT" --threads 4 --timeout 180 wsgi:app >"$LOG" 2>&1 & SRV_PID=$!; SERVER="gunicorn"
else
  "$PY" -m flask --app wsgi run --port "$PORT" >"$LOG" 2>&1 & SRV_PID=$!; SERVER="flask (dev)"
fi

printf "  ${DIM}waiting for the app to come up…${R}\n"
UP=0
for _ in $(seq 1 30); do
  [ "$(http_ok "http://127.0.0.1:$PORT/health")" = ok ] && { UP=1; break; }
  kill -0 "$SRV_PID" 2>/dev/null || { bad "server exited during startup:"; tail -n 15 "$LOG"; exit 1; }
  sleep 0.5
done
[ "$UP" = 1 ] && ok "web app responding ($SERVER)" || { bad "app did not respond on :$PORT"; tail -n 15 "$LOG"; exit 1; }

[ "$(hjson "http://127.0.0.1:$PORT/health/pdc" ok)" = True ] && ok "PDC: live data" \
  || { [ "$(hjson "http://127.0.0.1:$PORT/health/pdc" demo)" = True ] \
        && warn "PDC: demo data — switch to Live PDC in Settings, then Save & apply" \
        || warn "PDC: status unknown (auth on, or check Settings)"; }
[ "$(hjson "http://127.0.0.1:$PORT/health/llm" ok)" = True ] && ok "LLM: reachable" \
  || warn "LLM: offline — /chat uses the offline builder until Ollama is up"

step "Ready"
printf "  ${B}Web app${R}     ${CYN}http://localhost:%s${R}\n" "$PORT"
printf "  ${B}AI builder${R}  ${CYN}http://localhost:%s/chat${R}\n" "$PORT"
[ "$WITH_MCP" = 1 ] && printf "  ${B}MCP server${R}  http://localhost:8765 ${DIM}(external chat/agents)${R}\n"
printf "  ${DIM}Ctrl+C to stop.${R}\n\n"

wait "$SRV_PID"
