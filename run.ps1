<#
  run.ps1 - launch Catalog Insights on Windows (web app, optionally the MCP
            server) with preflight checks, hardware detection and a connection
            report. PowerShell twin of run.sh; run.bat remains as a wrapper.

    .\run.ps1                    web app only (all you need for local LLM)
    .\run.ps1 -Mcp               also start the MCP server (Claude Desktop / agents)
    .\run.ps1 -Gpu | -Cpu        force model sizing (default: auto-detect)
    .\run.ps1 -Pull              download the recommended Ollama model
    .\run.ps1 -Port 9000         web app port (default 5002, or INSIGHTS_PORT)
    .\run.ps1 -NoVenv            use the current Python instead of a .venv

  The web app runs in THIS console (Ctrl-C to stop), matching the Glossary
  and Policy launchers. The MCP server (if requested) gets its own window.
  Windows PowerShell 5.1 compatible.
#>
[CmdletBinding()]
param(
    [int]$Port = 0,
    [string]$BindHost = '',
    [switch]$Mcp,
    [switch]$Gpu,
    [switch]$Cpu,
    [switch]$Pull,
    [switch]$NoVenv
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Ok   ($m) { Write-Host "  [ok] $m" -ForegroundColor Green }
function Note ($m) { Write-Host "  [ !] $m" -ForegroundColor Yellow }
function Die  ($m) { Write-Host "  [xx] $m" -ForegroundColor Red; exit 1 }

$AppVersion = 'dev'
if (Test-Path VERSION) { $AppVersion = (Get-Content VERSION -Raw).Trim() }

Write-Host "===================================================================="
Write-Host "  Catalog Insights  v$AppVersion"
Write-Host "  AI-assisted reporting & dashboards for Pentaho Data Catalog"
Write-Host "===================================================================="
Write-Host ""
Write-Host "  Governance note: the ONLY write in the whole product is saving a"
Write-Host "  dashboard spec file locally. It never modifies the catalog."
Write-Host ""

Write-Host "Preflight"
# find a 3.9+ interpreter: py launcher (newest first), then python on PATH
$PyExe = $null; $PyPre = @()
foreach ($cand in @(@('py','-3.13'), @('py','-3.12'), @('py','-3.11'), @('py'), @('python'))) {
    if (-not (Get-Command $cand[0] -ErrorAction SilentlyContinue)) { continue }
    & $cand[0] $cand[1] -c "import sys;sys.exit(0 if sys.version_info>=(3,9) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { $PyExe = $cand[0]; if ($cand.Count -gt 1) { $PyPre = @($cand[1]) }; break }
}
if (-not $PyExe) { Die "Python 3.9+ required (3.12+ recommended)" }
function PyRun { & $script:PyExe ($script:PyPre + $args) }
Ok ("Python 3.9+ (" + (($PyExe + " " + ($PyPre -join ' ')).Trim()) + ")")

if (-not $NoVenv) {
    if (-not (Test-Path .venv)) {
        Note "creating .venv..."
        PyRun -m venv .venv
    }
    # from here on, the venv python is the interpreter
    $PyExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    $PyPre = @()
    Ok "virtualenv active (.venv)"
} else {
    Note "using current Python (-NoVenv)"
}
PyRun -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { Die "dependency install failed" }
Ok "web app dependencies installed"
if ($Mcp) {
    PyRun -m pip install -q -r requirements-mcp.txt
    if ($LASTEXITCODE -eq 0) { Ok "MCP dependencies installed" } else { Die "MCP dependency install failed" }
}

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Note ".env created from .env.example - EDIT IT with your PDC details, or set INSIGHTS_DEMO=true"
} else { Ok ".env present" }

# --- resolve port/host: parameter > env > .env > default ---------------------
function Get-DotEnv ($key, $default) {
    $line = Select-String -Path .env -Pattern ("^" + $key + "=") -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($line) { return $line.Line.Substring($key.Length + 1) } else { return $default }
}
if ($Port -eq 0) {
    if ($env:INSIGHTS_PORT) { $Port = [int]$env:INSIGHTS_PORT } else { $Port = [int](Get-DotEnv 'INSIGHTS_PORT' '5002') }
}
if (-not $BindHost) {
    if ($env:INSIGHTS_HOST) { $BindHost = $env:INSIGHTS_HOST } else { $BindHost = Get-DotEnv 'INSIGHTS_HOST' '0.0.0.0' }
}
$portState = PyRun tools\preflight.py port $Port
if ("$portState" -match 'busy') { Die "port $Port is in use - pass -Port <n>" } else { Ok "port $Port is free" }

# --- what this run targets ----------------------------------------------------
$pdcUrl   = Get-DotEnv 'PDC_BASE_URL' '(not set)'
$pdcVer   = Get-DotEnv 'PDC_API_VERSION' 'v3'
$pdcAuth  = Get-DotEnv 'PDC_AUTH_METHOD' 'auto'
$pdcTls   = Get-DotEnv 'PDC_VERIFY_TLS' 'true'
$demo     = Get-DotEnv 'INSIGHTS_DEMO' 'false'
$provider = Get-DotEnv 'LLM_PROVIDER' 'local'
$llmModel = Get-DotEnv 'LLM_MODEL' '(default)'
$llmUrl   = Get-DotEnv 'LLM_BASE_URL' 'http://localhost:11434'
Write-Host ""
Write-Host "This run will connect to"
if ($demo -eq 'true') {
    Write-Host "  PDC   DEMO MODE (bundled sample - no live PDC)"
} else {
    Write-Host "  PDC   $pdcUrl   (api $pdcVer, auth $pdcAuth, verify_tls $pdcTls)"
}
Write-Host "  LLM   $provider  $llmModel  @ $llmUrl"

# --- hardware & model ----------------------------------------------------------
Write-Host ""
Write-Host "Hardware & model"
$mode = 'cpu'
if ($Gpu) { $mode = 'gpu' }
elseif (-not $Cpu -and (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { $mode = 'gpu' }
$env:INSIGHTS_FORCE_MODE = $mode
if ($mode -eq 'cpu') { $env:OLLAMA_NUM_PARALLEL = '1' }
if ($mode -eq 'gpu') { Ok "GPU detected -> GPU model sizing" } else { Ok "no GPU -> CPU model sizing" }
$rec = PyRun -c "from app.model_advice import recommend;print(recommend('$mode')['model'])" 2>$null
if ($rec) { Write-Host "  recommended model: $rec" }
if ($provider -eq 'local') {
    $olst = PyRun tools\preflight.py http "$llmUrl/api/tags"
    if ("$olst" -match 'ok') { Ok "Ollama reachable at $llmUrl" } else { Note "Ollama not reachable at $llmUrl - /chat uses offline builder until it's up" }
    if ($Pull -and $rec) {
        if (Get-Command ollama -ErrorAction SilentlyContinue) { Write-Host "  pulling $rec..."; ollama pull $rec } else { Note "ollama not on PATH - skipping -Pull" }
    }
} else { Ok "LLM provider: $provider (no local Ollama needed)" }

# --- start ---------------------------------------------------------------------
Write-Host ""
if ($Mcp) {
    Ok "MCP server -> new window (:8765)"
    $env:MCP_HTTP = '1'   # inherited by the child window
    Start-Process -FilePath $PyExe -ArgumentList ($PyPre + @('-m','mcp_server.server')) -WorkingDirectory $PSScriptRoot
    Remove-Item Env:MCP_HTTP -ErrorAction SilentlyContinue
}
Write-Host "  Web app       http://127.0.0.1:$Port"
Write-Host "  AI builder    http://127.0.0.1:$Port/chat"
Write-Host "  Health        http://127.0.0.1:$Port/health/pdc"
Write-Host ""
Write-Host "  Ready - Ctrl-C to stop" -ForegroundColor Cyan
Write-Host ""
PyRun -m waitress --listen "${BindHost}:$Port" wsgi:app
