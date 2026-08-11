<#
.SYNOPSIS
    Stage the Python app + built React UI for bundling.

.DESCRIPTION
    Copies the app tree into src-tauri\vendor\app, which tauri.conf.json's
    bundle.resources maps to "app" inside the install.

    The staged tree MIRRORS the repo layout:

        app\boot.py            (desktop launcher - see desktop\boot.py)
        app\asgi.py
        app\VERSION            (app\main.py reads it for the version string)
        app\app\main.py        (the package)
        app\mcp_server\
        app\frontend\dist\index.html
        app\ui\mock\

    That is not cosmetic. app\main.py resolves the built UI as
    ROOT/frontend/dist - the repo root relative to the package - so flattening
    the tree would leave the server running with no UI to serve.

    Deliberately EXCLUDES local state and developer debris. Shipping a
    developer's .env would leak provider API keys and lab PDC hostnames into
    every install; a dashboard saved during development would ship someone
    else's experiment as a built-in.

    Built-in dashboards are staged FROM THE INDEX, not by globbing the
    directory: in a checkout, app\dashboards is also where saves land, so the
    directory can hold dashboards that are not built-ins. index.json is the
    authority on what ships.

.NOTES
    Windows PowerShell 5.1+. ASCII-only on purpose.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
# Without this an undefined variable expands to empty and robocopy just returns
# exit 16 - which is how the staging destination silently became "" once.
Set-StrictMode -Version Latest

$desktopDir = Split-Path -Parent $PSScriptRoot
$repoRoot   = Split-Path -Parent $desktopDir
$srcApp     = Join-Path $repoRoot "app"
$srcMcp     = Join-Path $repoRoot "mcp_server"
$srcUi      = Join-Path $repoRoot "frontend\dist"
$srcMock    = Join-Path $repoRoot "ui\mock"
$stageDir   = Join-Path $desktopDir "src-tauri\vendor\app"
$stageApp   = Join-Path $stageDir "app"
$stageUi    = Join-Path $stageDir "frontend\dist"

function Ok($m)   { Write-Host "  [ok] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [!]  $m" -ForegroundColor Yellow }

Write-Host ""
Write-Host "  Staging the app" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "asgi.py"))) {
    throw "asgi.py not found - is $repoRoot the repo root?"
}
if (-not (Test-Path -LiteralPath (Join-Path $srcUi "index.html"))) {
    throw "frontend\dist\index.html not found - run 'npm run build' in frontend\ first"
}

if (Test-Path -LiteralPath $stageDir) { Remove-Item -LiteralPath $stageDir -Recurse -Force }
New-Item -ItemType Directory -Path $stageDir -Force | Out-Null

# State files and secrets: never shipped. The installed app starts on the
# bundled sample and writes to the per-user state directory (see app\paths.py).
$excludeFiles = @(".env", ".env.example", "audit.log", "*.log")
$excludeDirs  = @(".venv", "venv", "__pycache__", ".pytest_cache",
                  # Staged separately from index.json below - see .DESCRIPTION.
                  "dashboards")

# robocopy: mirror of a clean tree, /XD and /XF do the excluding.
# Exit codes 0-7 are success (8+ is a real failure) - a quirk worth pinning,
# because treating any non-zero as failure makes every build look broken.
#
# /XD names are RELATIVE on purpose: an absolute path excludes only that exact
# directory, so "app\__pycache__" left every SUBPACKAGE's __pycache__ in the
# stage - and the 1.17.0 installer shipped bytecode caches from the dev
# checkout into Program Files, where the uninstaller (which only deletes what
# it shipped by name) still removed them, but only because they were
# enumerated at build time. A relative name matches the directory at any depth.
$roboArgs = @($srcApp, $stageApp, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP")
foreach ($d in $excludeDirs)  { $roboArgs += @("/XD", $d) }
foreach ($f in $excludeFiles) { $roboArgs += @("/XF", $f) }
& robocopy @roboArgs | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed staging the app package (exit $LASTEXITCODE)" }

# The built-in dashboards, from the index. Anything in the directory that the
# index does not list is a developer's save, not a built-in, and stays behind.
$srcDash   = Join-Path $srcApp "dashboards"
$stageDash = Join-Path $stageApp "dashboards"
$idxFile   = Join-Path $srcDash "index.json"
if (-not (Test-Path -LiteralPath $idxFile)) {
    throw "app\dashboards\index.json not found - run tools\build_dashboards.py first"
}
New-Item -ItemType Directory -Path $stageDash -Force | Out-Null
Copy-Item -LiteralPath $idxFile -Destination (Join-Path $stageDash "index.json") -Force
$readme = Join-Path $srcDash "README.md"
if (Test-Path -LiteralPath $readme) {
    Copy-Item -LiteralPath $readme -Destination (Join-Path $stageDash "README.md") -Force
}
$idx = Get-Content -LiteralPath $idxFile -Raw | ConvertFrom-Json
$staged = 0
foreach ($section in $idx.PSObject.Properties.Name) {
    $secDir = Join-Path $stageDash $section
    New-Item -ItemType Directory -Path $secDir -Force | Out-Null
    foreach ($entry in $idx.$section) {
        $name = "$($entry.id).studio.json"
        $src = Join-Path (Join-Path $srcDash $section) $name
        if (-not (Test-Path -LiteralPath $src)) {
            throw "index.json lists $section/$name but the file is missing - run tools\build_dashboards.py"
        }
        Copy-Item -LiteralPath $src -Destination (Join-Path $secDir $name) -Force
        $staged++
    }
}
Ok "staged $staged built-in dashboard(s) from index.json"

# The MCP server package (Claude Desktop / external agents). /XD names are
# relative here for the same reason as above.
& robocopy $srcMcp (Join-Path $stageDir "mcp_server") "/E" "/NFL" "/NDL" "/NJH" "/NJS" "/NP" `
    "/XD" "__pycache__" ".venv" "venv" | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed staging mcp_server (exit $LASTEXITCODE)" }

# The built SPA and the static design mock (served at /mock for reference).
New-Item -ItemType Directory -Path $stageUi -Force | Out-Null
& robocopy $srcUi $stageUi "/E" "/NFL" "/NDL" "/NJH" "/NJS" "/NP" | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed staging the UI (exit $LASTEXITCODE)" }
& robocopy $srcMock (Join-Path $stageDir "ui\mock") "/E" "/NFL" "/NDL" "/NJH" "/NJS" "/NP" | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed staging ui\mock (exit $LASTEXITCODE)" }

# Root files the server reads at runtime.
Copy-Item -LiteralPath (Join-Path $repoRoot "asgi.py") -Destination (Join-Path $stageDir "asgi.py") -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "VERSION") -Destination (Join-Path $stageDir "VERSION") -Force

# boot.py puts the app root on sys.path before importing it. The embeddable
# runtime's ._pth replaces sys.path outright, so without this the server cannot
# import asgi.py whatever working directory it is given. See desktop\boot.py.
Copy-Item -LiteralPath (Join-Path $desktopDir "boot.py") -Destination (Join-Path $stageDir "boot.py") -Force

# Belt and braces: prove nothing sensitive slipped through. A rename or a new
# state file would otherwise be caught only by a customer.
$leaked = Get-ChildItem -LiteralPath $stageDir -Recurse -File |
    Where-Object { $_.Name -eq ".env" -or $_.Name -eq "audit.log" }
if ($leaked) {
    $leaked | ForEach-Object { Warn ("leaked: " + $_.FullName) }
    throw "state or secret files reached the staging tree - fix the exclude list"
}

# Same guard for dev virtualenvs. The staged tree runs on the VENDORED
# runtime, so a bundled venv is a second, wrong Python - PDC-Policy shipped
# one in every installer until someone listed the exe (934f61c there). The
# excludes above prevent it; this proves it, for every tree staged above.
$venvs = Get-ChildItem -LiteralPath $stageDir -Recurse -Directory |
    Where-Object { $_.Name -eq ".venv" -or $_.Name -eq "venv" }
if ($venvs) {
    $venvs | ForEach-Object { Warn ("venv: " + $_.FullName) }
    throw "a dev virtualenv reached the staging tree - fix the exclude list"
}

# The paths the shell and the server actually depend on. Assert them here,
# where the fix is obvious, rather than at first launch on a customer's laptop.
foreach ($must in @((Join-Path $stageDir "asgi.py"),
                    (Join-Path $stageDir "boot.py"),
                    (Join-Path $stageDir "VERSION"),
                    (Join-Path $stageApp "main.py"),
                    (Join-Path $stageApp "schema\dashboard.schema.json"),
                    (Join-Path $stageDash "index.json"),
                    (Join-Path $stageUi  "index.html"),
                    (Join-Path $stageDir "mcp_server\server.py"))) {
    if (-not (Test-Path -LiteralPath $must)) { throw "staging incomplete: $must is missing" }
}

# Prove the staged tree can actually be imported, using the runtime that will
# ship with it. File-existence checks cannot catch a module excluded by mistake;
# this can, and it costs a few seconds.
$vendorPy = Join-Path $desktopDir "src-tauri\vendor\python\python.exe"
if (Test-Path -LiteralPath $vendorPy) {
    $probe = "import sys; sys.path.insert(0, sys.argv[1]); import asgi; import mcp_server.server; print('import ok')"
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    # -B: do NOT write bytecode. Without it this check compiles __pycache__ into
    # the tree robocopy just finished excluding it from, and those .pyc files
    # then ship - stale caches for a Python version the user may not even be
    # running. The check has to leave the stage exactly as it found it.
    $out = & $vendorPy -B -c $probe $stageDir 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    if ($code -ne 0) {
        $out | ForEach-Object { Warn $_ }
        throw "the staged tree cannot import asgi.py - a module is missing from the stage"
    }
    # Belt and braces: -B covers this run, but anything else that touches the
    # stage (a stray manual test, a future check) would leave caches behind, and
    # a shipped .pyc is invisible until someone lists the installer.
    Get-ChildItem -LiteralPath $stageDir -Recurse -Directory -Filter "__pycache__" |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }

    Ok "staged tree imports cleanly"
} else {
    Warn "no vendored runtime yet - skipping the import check (run fetch:python first)"
}

$count = (Get-ChildItem -LiteralPath $stageDir -Recurse -File).Count
Ok "staged $count file(s) to src-tauri\vendor\app"
Write-Host ""

# robocopy returns 1 for "files were copied" and PowerShell surfaces the LAST
# native exit code as the script's, so a successful run would look like a
# failure to npm and abort the tauri build.
exit 0
