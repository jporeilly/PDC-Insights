@echo off
REM run.bat - launch Catalog Insights (web app, optionally the MCP server) with
REM           preflight checks, hardware detection, and a post-start health report.
REM
REM   run.bat                 web app only (all you need for local LLM)
REM   run.bat --mcp           also start the MCP server (Claude Desktop / agents)
REM   run.bat --gpu | --cpu   force model sizing (default: auto-detect)
REM   run.bat --pull          download the recommended Ollama model
REM   run.bat --port 9000     web app port (default 8660)
REM   run.bat --no-venv       use the current Python instead of a .venv
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PORT=8660"
set "WITH_MCP=0"
set "FORCE="
set "PULL=0"
set "USE_VENV=1"

set "APP_VERSION=dev"
if exist VERSION ( for /f "usebackq delims=" %%v in ("VERSION") do set "APP_VERSION=%%v" )

:parse
if "%~1"=="" goto endparse
if /i "%~1"=="--mcp"     set "WITH_MCP=1"
if /i "%~1"=="--gpu"     set "FORCE=gpu"
if /i "%~1"=="--cpu"     set "FORCE=cpu"
if /i "%~1"=="--pull"    set "PULL=1"
if /i "%~1"=="--no-venv" set "USE_VENV=0"
if /i "%~1"=="--port"    ( set "PORT=%~2" & shift )
if /i "%~1"=="-h"        goto help
if /i "%~1"=="--help"    goto help
shift
goto parse
:endparse

echo ====================================================================
echo   Catalog Insights  v%APP_VERSION%
echo   AI-assisted reporting ^& dashboards for Pentaho Data Catalog
echo ====================================================================
echo.
echo   What it is
echo     - Reads your PDC catalog READ-ONLY via the public API ^(never writes^).
echo     - Uses a LOCAL LLM ^(Ollama^) to turn plain-English asks into dashboard
echo       specs built from your real catalog - nothing leaves the box.
echo     - Serves a web UI ^(trust / quality / sensitivity / sources^) plus an
echo       optional MCP server for Claude Desktop and agents.
echo.
echo   Governance note: the ONLY write in the whole product is saving a
echo   dashboard spec file locally. It never modifies the catalog.
echo.

echo Preflight
python -c "import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" && (echo   [ok] Python 3.9+) || (echo   [xx] Python 3.9+ required & exit /b 1)

if "%USE_VENV%"=="1" (
  if not exist .venv ( echo   [ !] creating .venv... & python -m venv .venv )
  call .venv\Scripts\activate.bat
  echo   [ok] virtualenv active ^(.venv^)
) else ( echo   [ !] using current Python ^(--no-venv^) )

echo   installing dependencies...
pip install -q -r requirements.txt && echo   [ok] web app dependencies installed
if "%WITH_MCP%"=="1" ( pip install -q -r requirements-mcp.txt && echo   [ok] MCP dependencies installed )

if not exist .env ( copy .env.example .env >nul & echo   [ !] .env created from .env.example - EDIT IT with your PDC details, or set INSIGHTS_DEMO=true ) else ( echo   [ok] .env present )

for /f %%p in ('python tools\preflight.py port %PORT%') do set "PORTST=%%p"
if /i "%PORTST%"=="busy" ( echo   [xx] port %PORT% is in use - pass --port N & exit /b 1 ) else ( echo   [ok] port %PORT% is free )

REM --- read the connection config from .env so the operator sees what this run targets ---
set "PDC_URL=(not set)"
for /f "tokens=1,* delims==" %%a in ('findstr /b "PDC_BASE_URL=" .env 2^>nul') do set "PDC_URL=%%b"
set "PDC_VER=v3"
for /f "tokens=1,* delims==" %%a in ('findstr /b "PDC_API_VERSION=" .env 2^>nul') do set "PDC_VER=%%b"
set "PDC_AUTH=auto"
for /f "tokens=1,* delims==" %%a in ('findstr /b "PDC_AUTH_METHOD=" .env 2^>nul') do set "PDC_AUTH=%%b"
set "PDC_TLS=true"
for /f "tokens=1,* delims==" %%a in ('findstr /b "PDC_VERIFY_TLS=" .env 2^>nul') do set "PDC_TLS=%%b"
set "DEMO=false"
for /f "tokens=1,* delims==" %%a in ('findstr /b "INSIGHTS_DEMO=" .env 2^>nul') do set "DEMO=%%b"
set "PROVIDER=local"
for /f "tokens=1,* delims==" %%a in ('findstr /b "LLM_PROVIDER=" .env 2^>nul') do set "PROVIDER=%%b"
set "LLM_MODEL=(default)"
for /f "tokens=1,* delims==" %%a in ('findstr /b "LLM_MODEL=" .env 2^>nul') do set "LLM_MODEL=%%b"
set "LLM_URL=http://localhost:11434"
for /f "tokens=1,* delims==" %%a in ('findstr /b "LLM_BASE_URL=" .env 2^>nul') do set "LLM_URL=%%b"

echo.
echo This run will connect to
if /i "%DEMO%"=="true" (
  echo   PDC   DEMO MODE ^(bundled sample - no live PDC^)
) else (
  echo   PDC   %PDC_URL%   ^(api %PDC_VER%, auth %PDC_AUTH%, verify_tls %PDC_TLS%^)
)
echo   LLM   %PROVIDER%  %LLM_MODEL%  @ %LLM_URL%

echo.
echo Hardware ^& model
set "MODE=%FORCE%"
if "%MODE%"=="" ( where nvidia-smi >nul 2>nul && ( set "MODE=gpu" ) || ( set "MODE=cpu" ) )
set "INSIGHTS_FORCE_MODE=%MODE%"
if /i "%MODE%"=="cpu" set "OLLAMA_NUM_PARALLEL=1"
if /i "%MODE%"=="gpu" ( echo   [ok] GPU detected -^> GPU model sizing ) else ( echo   [ok] no GPU -^> CPU model sizing )

for /f "delims=" %%i in ('python -c "from app.model_advice import recommend;print(recommend('%MODE%')['model'])" 2^>nul') do set "REC=%%i"
if defined REC echo   recommended model: !REC!

if /i "%PROVIDER%"=="local" (
  for /f %%h in ('python tools\preflight.py http %LLM_URL%/api/tags') do set "OLST=%%h"
  if /i "!OLST!"=="ok" ( echo   [ok] Ollama reachable at %LLM_URL% ) else ( echo   [ !] Ollama not reachable at %LLM_URL% - /chat uses offline builder until it's up )
  if "%PULL%"=="1" if defined REC (
    where ollama >nul 2>nul && ( echo   pulling !REC!... & ollama pull !REC! ) || echo   [ !] ollama not on PATH - skipping --pull
  )
) else ( echo   [ok] LLM provider: %PROVIDER% ^(no local Ollama needed^) )

echo.
echo Starting
if "%WITH_MCP%"=="1" (
  echo   [ok] MCP server -^> new window ^(:8765^)
  start "Catalog Insights MCP" cmd /k "call .venv\Scripts\activate.bat 2>nul & set MCP_HTTP=1 & python -m mcp_server.server"
)
echo   [ok] web app -^> new window ^(waitress :%PORT%^)
start "Catalog Insights Web" cmd /k "call .venv\Scripts\activate.bat 2>nul & set INSIGHTS_FORCE_MODE=%MODE% & (where waitress-serve >nul 2>nul && waitress-serve --port=%PORT% wsgi:app || python -m flask --app wsgi run --port %PORT%)"

echo   waiting for the app to come up...
set "UP=0"
for /l %%n in (1,1,30) do (
  if "!UP!"=="0" (
    for /f %%h in ('python tools\preflight.py http http://127.0.0.1:%PORT%/health') do if /i "%%h"=="ok" set "UP=1"
    if "!UP!"=="0" ( ping -n 2 127.0.0.1 >nul )
  )
)
if "!UP!"=="1" ( echo   [ok] web app responding ) else ( echo   [xx] app did not respond on :%PORT% - check the web window )

for /f %%v in ('python tools\preflight.py json http://127.0.0.1:%PORT%/health/pdc ok') do set "PDCOK=%%v"
for /f %%v in ('python tools\preflight.py json http://127.0.0.1:%PORT%/health/pdc demo') do set "PDCDEMO=%%v"
for /f %%v in ('python tools\preflight.py json http://127.0.0.1:%PORT%/health/llm ok') do set "LLMOK=%%v"
if /i "%PDCOK%"=="True" ( echo   [ok] PDC: live data ) else ( if /i "%PDCDEMO%"=="True" ( echo   [ !] PDC: demo data - switch to Live PDC in Settings, then Save ^& apply ) else ( echo   [ !] PDC: status unknown ^(auth on, or check Settings^) ) )
if /i "%LLMOK%"=="True" ( echo   [ok] LLM: reachable ) else ( echo   [ !] LLM: offline - /chat uses the offline builder until Ollama is up )

echo.
echo ====================================================================
echo  Ready - Catalog Insights v%APP_VERSION%
echo ====================================================================
echo   Web app       http://localhost:%PORT%
echo   AI builder    http://localhost:%PORT%/chat
echo   Settings      http://localhost:%PORT%  ^(Configure -^> Settings^)
if "%WITH_MCP%"=="1" echo   MCP server    http://localhost:8765  ^(external chat / agents^)
echo.
echo   Diagnostics ^(admin, in the browser^)
echo     Health      http://localhost:%PORT%/health/pdc
echo     Auth token  http://localhost:%PORT%/health/pdc/token   ^(decoded claims^)
echo     Live probe  http://localhost:%PORT%/health/pdc/probe   ^(per-read results^)
echo.
echo   If it shows demo data: open Settings, set Data source = Live PDC, Save ^& apply.
echo   The app^(+MCP^) run in their own windows; close those windows to stop.
goto :eof

:help
echo run.bat - start the Catalog Insights web app, and optionally the MCP server.
echo.
echo   Catalog Insights reads your Pentaho Data Catalog ^(read-only^) and uses a
echo   local LLM to build dashboards from your real catalog data.
echo.
echo   run.bat                 web app only ^(all you need for local LLM^)
echo   run.bat --mcp           web app + MCP server ^(for Claude Desktop / agents^)
echo   run.bat --gpu ^| --cpu   force model sizing ^(default: auto-detect^)
echo   run.bat --pull          also download the recommended Ollama model
echo   run.bat --port 9000     serve the web app on a different port ^(default 8660^)
echo   run.bat --no-venv       use the current Python instead of a .venv
echo.
echo   Configure the PDC connection in .env ^(PDC_BASE_URL, PDC_USERNAME,
echo   PDC_PASSWORD, PDC_AUTH_METHOD, PDC_VERIFY_TLS^). The local LLM ^(Ollama^) is
echo   used directly by the web app - you do NOT need the MCP server for it.
goto :eof
