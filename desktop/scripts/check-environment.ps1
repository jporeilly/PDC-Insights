<#
.SYNOPSIS
    Post-install environment check: what is missing, and how to fix it.

.DESCRIPTION
    Reports rather than blocks. Only WebView2 and a usable Python are FAIL,
    because without them the window does not open. Ollama absent is a WARN
    (the app also drives Anthropic and OpenAI/Azure from its Settings page),
    and PDC unreachable is a WARN (demo mode covers every dashboard until a
    server is configured). Treating those as hard failures would teach people
    to ignore the output.

    Runs from BOTH layouts: an installed $INSTDIR\provisioning\ and a checkout
    desktop\scripts\. The shared resolvers in lib\common.ps1 understand both.

.PARAMETER PdcUrl
    PDC base URL to probe. Defaults to PDC_BASE_URL (environment, then the
    state-dir .env), then asks - unless -NoPrompt or -Json.

.PARAMETER NoPrompt
    Never ask questions. For provisioning runs (the installer uses this).

.PARAMETER Json
    Emit machine-readable results and nothing else on stdout.

.EXAMPLE
    .\check-environment.ps1 -PdcUrl https://catalog.example.com

.EXAMPLE
    .\check-environment.ps1 -NoPrompt -Json

.NOTES
    Windows PowerShell 5.1+. ASCII-only on purpose.
#>
[CmdletBinding()]
param(
    [string]$PdcUrl,
    [switch]$NoPrompt,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$script:Checks   = @()
$script:Failures = 0
$script:Warnings = 0
$script:Fixes    = @()

function Say {
    param([string]$Text = "", [string]$Colour = "Gray")
    if (-not $Json) { Write-Host $Text -ForegroundColor $Colour }
}

function Report {
    param(
        [string]$Name,
        [ValidateSet("OK", "FAIL", "WARN", "SKIP")][string]$State,
        [string]$Detail = "",
        [string]$Fix = ""
    )
    $script:Checks += [ordered]@{ name = $Name; state = $State; detail = $Detail; fix = $Fix }
    if (-not $Json) {
        $colour = @{ OK = "Green"; FAIL = "Red"; WARN = "Yellow"; SKIP = "DarkGray" }[$State]
        Write-Host ("  [{0,-4}] " -f $State) -ForegroundColor $colour -NoNewline
        Write-Host ("{0,-30}" -f $Name) -NoNewline
        Write-Host $Detail -ForegroundColor DarkGray
    }
    if ($State -eq "FAIL") {
        $script:Failures++
        if ($Fix) { $script:Fixes += "  # $Name`n  $Fix" }
    } elseif ($State -eq "WARN") {
        $script:Warnings++
        if ($Fix) { $script:Fixes += "  # $Name (optional)`n  $Fix" }
    }
}

# 127.0.0.1 rather than "localhost": localhost can resolve to ::1 first, and the
# probe then reports a healthy service as down.
function Test-Port([string]$TargetHost, [int]$Port, [int]$TimeoutMs = 1500) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect($TargetHost, $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if ($ok) { $c.EndConnect($iar) }
        $c.Close()
        return $ok
    } catch { return $false }
}

. (Join-Path $PSScriptRoot "lib\common.ps1")

$script:AppRoot = Resolve-AppRoot $PSScriptRoot

Say ""
Say "  PDC Catalog Insights - environment check" "Cyan"
Say "  Reports what is missing and how to fix it. Only WebView2 and Python are" "DarkGray"
Say "  hard requirements; everything else is optional and says so." "DarkGray"
Say ""

# -- the two things that stop the window opening ----------------------------
Say "  Required" "Cyan"

# WebView2. The installer bundles the bootstrapper, so this should already be
# satisfied on a machine that ran it; the check matters for a machine being
# prepared for the app, or one where the runtime was removed.
$wv2Keys = @(
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    "HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
)
$wv2 = $null
foreach ($k in $wv2Keys) {
    if (Test-Path $k) {
        try {
            $v = (Get-ItemProperty -Path $k -ErrorAction Stop).pv
            if ($v) { $wv2 = $v; break }
        } catch {}
    }
}
if ($wv2) {
    Report "WebView2 runtime" "OK" $wv2
} else {
    Report "WebView2 runtime" "FAIL" "not found - the app window cannot render" `
        "winget install -e --id Microsoft.EdgeWebView2Runtime"
}

# Python. Resolve-PyExe knows both layouts: $INSTDIR\python for an install,
# desktop\src-tauri\vendor\python for a checkout, then PATH.
$script:PyExe = Resolve-PyExe $PSScriptRoot
$bundled = $script:PyExe -and (Test-Path -LiteralPath $script:PyExe) -and
           ($script:PyExe -like "*\python\python.exe")

if (-not $script:PyExe) {
    Report "Python 3.10+" "FAIL" "no interpreter found, bundled or on PATH" `
        "reinstall the app, or install Python: winget install -e --id Python.Python.3.12"
} else {
    $ver = & $script:PyExe -c "import sys;print('.'.join(map(str,sys.version_info[:3])))" 2>$null
    if ($bundled) {
        Report "Python (bundled)" "OK" ("" + $ver + " - shipped with the app, nothing to install")
    } else {
        Report "Python 3.10+" "OK" ("" + $ver + " - from PATH (running from a checkout)")
    }

    # The imports that actually break in a packaged build. A runtime that starts
    # but cannot import its packages is the failure this whole check exists for,
    # and confirming python.exe merely EXISTS would miss it entirely.
    $probe = & $script:PyExe -c "import uvicorn,fastapi,requests,jsonschema,dotenv,mcp;print('ok')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Report "Python dependencies" "OK" "uvicorn, fastapi, requests, jsonschema, dotenv, mcp"
    } elseif ($bundled) {
        Report "Python dependencies" "FAIL" "the bundled runtime cannot import its own packages" `
            "the install is incomplete - reinstall"
    } else {
        Report "Python dependencies" "WARN" "not importable from this interpreter" `
            "run.ps1 builds a venv with them; this only matters for a checkout"
    }
}

# -- state -------------------------------------------------------------------
Say ""
Say "  State" "Cyan"

# Through the shared resolver, for the same reason as the interpreter above: a
# check that probes a different directory from the one the app writes to is
# worse than no check.
$state    = Resolve-StateDir $PSScriptRoot
$stateDir = $state.Path
$stateWhy = $state.Why

if (Test-DirWritable $stateDir) {
    Report "State directory" "OK" "$stateDir ($stateWhy)"
} else {
    Report "State directory" "FAIL" "$stateDir is not writable" `
        "set INSIGHTS_STATE_DIR to a writable path, e.g. `$env:INSIGHTS_STATE_DIR='$env:APPDATA\PDC-Insights'"
}

# The state-dir .env is where Settings persists. Absent is normal on a fresh
# install (the app starts in demo mode); worth naming so "where did my settings
# go" has an answer.
$envFile = Join-Path $stateDir ".env"
$envLines = @()
if (Test-Path -LiteralPath $envFile) {
    $envLines = Get-Content -LiteralPath $envFile
    Report "Settings (.env)" "OK" $envFile
} else {
    Report "Settings (.env)" "SKIP" "none yet - the app writes it on the first Save and apply"
}

function EnvVal([string]$Key) {
    $v = [Environment]::GetEnvironmentVariable($Key)
    if ($v) { return $v }
    $line = $envLines | Where-Object { $_ -match ('^\s*' + $Key + '\s*=') } | Select-Object -First 1
    if ($line) { return ($line -split "=", 2)[1].Trim().Trim('"').Trim("'") }
    return $null
}

$demoVal = EnvVal "INSIGHTS_DEMO"
if ($demoVal -and ($demoVal.ToLower() -in @("1", "true", "yes", "on"))) {
    Report "Data mode" "OK" "demo - every dashboard runs on the bundled sample"
} elseif (EnvVal "PDC_BASE_URL") {
    Report "Data mode" "OK" "live - reading from PDC"
} else {
    Report "Data mode" "OK" "no PDC configured - the app falls back to the sample"
}

$freeGb = $null
try {
    $drive = (Get-Item -LiteralPath $stateDir).PSDrive
    if ($drive -and $drive.Free) { $freeGb = [math]::Round($drive.Free / 1GB, 1) }
} catch {}
if ($null -eq $freeGb) {
    Report "Disk space" "SKIP" "could not determine free space"
} elseif ($freeGb -lt 2) {
    Report "Disk space" "WARN" "$freeGb GB free - a local model needs several GB" "free up space on the state drive"
} else {
    Report "Disk space" "OK" "$freeGb GB free"
}

# -- LLM ---------------------------------------------------------------------
Say ""
Say "  Language model (optional - the deterministic builder works without one)" "Cyan"

$ollamaUp = Test-Port "127.0.0.1" 11434

# WHICH model to pull is the app's decision, not this script's. model_advice.py
# sizes a model to the actual hardware - VRAM first, then RAM - and naming one
# here would be a second rule that quietly disagrees with what the app's own
# Settings page recommends.
$recModel  = $null
$recReason = $null
$hwDetail  = $null
if ($script:PyExe -and $script:AppRoot) {
    # SINGLE quotes inside the Python. PowerShell strips embedded double quotes
    # when passing arguments to a native executable, so a dict written with "..."
    # keys arrives as bare names and dies with NameError.
    $probe = @'
import json, sys
sys.path.insert(0, sys.argv[1])
from app.model_advice import recommend
r = recommend()
print(json.dumps({'model': r['model'], 'reason': r['why'], 'mode': r['mode'],
                  'ram': r.get('ram_gb'), 'vram': r.get('vram_gb')}))
'@
    try {
        $out = & $script:PyExe -c $probe $script:AppRoot 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) {
            $d = $out | ConvertFrom-Json
            $recModel  = $d.model
            $recReason = $d.reason
            if ($d.mode -eq "gpu") {
                $hwDetail = "GPU, " + $d.vram + " GB VRAM"
            } else {
                $hwDetail = "CPU only, " + $d.ram + " GB RAM"
            }
        }
    } catch {}
}
if ($recModel) {
    Report "Hardware / model sizing" "OK" ("$hwDetail -> $recModel")
} else {
    Report "Hardware / model sizing" "SKIP" "could not run the app's detector - see the Settings page"
}

# The fix text follows the detector. With no detector we say where to look
# rather than inventing a model name.
if ($recModel) {
    $pullFix = "ollama pull $recModel   # $recReason"
} else {
    $pullFix = "open the app's Settings page - it recommends a model for this machine"
}

if ($ollamaUp) {
    $models = @()
    try {
        $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 4 -ErrorAction Stop
        if ($tags -and $tags.PSObject.Properties.Name -contains "models") {
            $models = @($tags.models | ForEach-Object { $_.name })
        }
    } catch {}
    if ($models.Count -eq 0) {
        # Up but empty is the trap: the app connects, then every generate call
        # fails, which reads as "the AI is broken" rather than "no model".
        Report "Ollama" "WARN" "running on 11434 but NO model pulled" $pullFix
    } elseif ($recModel -and ($models -notcontains $recModel)) {
        # Has models, but not the one sized to this hardware. Not a problem -
        # any of them will work - so this is information, not a warning.
        Report "Ollama" "OK" ("" + $models.Count + " model(s); recommended $recModel not among them")
    } else {
        Report "Ollama" "OK" ("" + $models.Count + " model(s): " + (($models | Select-Object -First 3) -join ", "))
    }
} else {
    Report "Ollama" "WARN" "not running on 11434" `
        ("winget install -e --id Ollama.Ollama" + [Environment]::NewLine + "  " + $pullFix)
}

# Hosted providers: presence only. Never print or log a key. The app reads
# LLM_PROVIDER / LLM_API_KEY from its .env (Settings page writes them).
$provider = EnvVal "LLM_PROVIDER"
$hasKey   = [bool](EnvVal "LLM_API_KEY")
if ($provider -in @("anthropic", "openai")) {
    if ($hasKey) {
        Report "Hosted LLM provider" "OK" "$provider configured, key present"
    } else {
        Report "Hosted LLM provider" "WARN" "$provider configured but no LLM_API_KEY" `
            "set the API key on the app's Settings page"
    }
} elseif (-not $ollamaUp) {
    Report "Hosted LLM provider" "SKIP" "not configured - chat falls back to the deterministic builder until Ollama or a key is set"
} else {
    Report "Hosted LLM provider" "SKIP" "not configured - using Ollama"
}

# -- Cloudflare Access --------------------------------------------------------
# Presence only, never the values. A service token is the only way a
# NON-BROWSER client gets through Cloudflare Access; the app reads
# PDC_CF_ACCESS_CLIENT_ID / _SECRET from its .env or the environment.
$cfId  = EnvVal "PDC_CF_ACCESS_CLIENT_ID"
$cfSec = EnvVal "PDC_CF_ACCESS_CLIENT_SECRET"
$looksTemplated = ($cfId -match "[<>]") -or ($cfSec -match "[<>]")
if ($cfId -and $cfSec -and $looksTemplated) {
    Report "Cloudflare Access token" "WARN" "still contains <placeholders> - the template was set, not the values" `
        "set the real Client ID and Secret from Zero Trust > Access > Service Auth"
} elseif ($cfId -and $cfSec -and ($cfId -notmatch "\.access$")) {
    Report "Cloudflare Access token" "WARN" "Client ID does not end in '.access' - check it was copied whole" `
        "Zero Trust > Access > Service Auth shows the full Client ID"
} elseif ($cfId -and $cfSec) {
    Report "Cloudflare Access token" "OK" "service token configured"
} elseif ($cfId -or $cfSec) {
    Report "Cloudflare Access token" "WARN" "only half the pair is set - both are required" `
        "set whichever of PDC_CF_ACCESS_CLIENT_ID / PDC_CF_ACCESS_CLIENT_SECRET is missing"
} else {
    Report "Cloudflare Access token" "SKIP" "not set - fine when PDC is reached directly"
}

# -- PDC ---------------------------------------------------------------------
Say ""
Say "  Pentaho Data Catalog (optional at install time)" "Cyan"

# NO default host. This check runs against whatever PDC the operator actually
# has, and guessing one would either probe a stranger's server or report a
# healthy machine as broken because someone else's host is down.
$pdcWhy = $null
if ($PdcUrl) { $pdcWhy = "-PdcUrl" }
if (-not $PdcUrl) {
    $PdcUrl = EnvVal "PDC_BASE_URL"
    if ($PdcUrl) { $pdcWhy = "PDC_BASE_URL (environment or .env)" }
}
# Ask, but only when a person is there to answer. -Json and -NoPrompt are for
# provisioning runs, where a blocked prompt would hang the whole job.
if (-not $PdcUrl -and -not $Json -and -not $NoPrompt -and [Environment]::UserInteractive) {
    Say ""
    Say "  No PDC server is configured yet." "DarkGray"
    Say "  Enter one to check it now, or press Enter to skip." "DarkGray"
    $answer = Read-Host "  PDC base URL (e.g. https://catalog.example.com)"
    if ($answer) {
        $PdcUrl = $answer.Trim()
        $pdcWhy = "entered now - not saved; set it on the app's Settings page to keep it"
    }
}

if (-not $PdcUrl) {
    Report "PDC" "SKIP" "no server configured - the app runs on the bundled sample until one is set"
} else {

# PDC routes by vhost. A bare IP answers 401 on every path, which looks like bad
# credentials and sends people to reset passwords that were never wrong.
if ($PdcUrl -match '^https?://(\d{1,3}\.){3}\d{1,3}(:\d+)?/?$') {
    Report "PDC URL" "WARN" "$PdcUrl is a bare IP - PDC routes by vhost and will answer 401 everywhere" `
        "use the server's hostname instead of its IP address"
} else {
    Report "PDC URL" "OK" ("$PdcUrl (from $pdcWhy)")
}

# Any HTTP answer proves reachability; 401/403 means PDC is up and asking for
# credentials, which at install time is a perfectly good result.
function Test-Pdc([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        return @{ Reached = $true; Detail = "HTTP " + $r.StatusCode; Tls = $true }
    } catch {
        $resp = $null
        try { $resp = $_.Exception.Response } catch {}
        if ($resp) {
            return @{ Reached = $true
                      Detail  = "HTTP " + [int]$resp.StatusCode + " - up, credentials are entered in the app"
                      Tls     = $true }
        }
        return @{ Reached = $false; Detail = $_.Exception.Message; Tls = $true }
    }
}

$pdc = Test-Pdc $PdcUrl

# A self-signed certificate is NOT unreachability, and reporting it as such
# sends people to check firewalls and DNS for a server that is answering
# perfectly well. Retry with validation off purely to tell the two apart.
if (-not $pdc.Reached -and $pdc.Detail -match 'trust relationship|SSL|TLS|certificate') {
    $saved = [System.Net.ServicePointManager]::CertificatePolicy
    try {
        Add-Type -TypeDefinition @'
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class PdcCheckCertPolicy : ICertificatePolicy {
    public bool CheckValidationResult(ServicePoint sp, X509Certificate c, WebRequest r, int p) { return true; }
}
'@ -ErrorAction SilentlyContinue
        [System.Net.ServicePointManager]::CertificatePolicy = New-Object PdcCheckCertPolicy
        $retry = Test-Pdc $PdcUrl
        if ($retry.Reached) { $pdc = @{ Reached = $true; Detail = $retry.Detail; Tls = $false } }
    } finally {
        [System.Net.ServicePointManager]::CertificatePolicy = $saved
    }
}

if ($pdc.Reached -and $pdc.Tls) {
    Report "PDC reachable" "OK" $pdc.Detail
} elseif ($pdc.Reached) {
    # Expected on a lab VM. Worth naming precisely, because the same symptom on
    # a customer machine means something quite different.
    Report "PDC reachable" "WARN" ($pdc.Detail + " - certificate is not trusted (self-signed)") `
        "expected on a lab VM; trust the cert, or set PDC_VERIFY_TLS=false on the Settings page"
} else {
    Report "PDC reachable" "WARN" "$PdcUrl - $($pdc.Detail)" `
        "check the hostname and that the server is up; every dashboard still works on the sample"
}

}   # end: a PDC server was configured

# -- summary -----------------------------------------------------------------
if ($Json) {
    [ordered]@{
        failures = $script:Failures
        warnings = $script:Warnings
        checks   = $script:Checks
    } | ConvertTo-Json -Depth 5
    exit ([int]($script:Failures -gt 0))
}

Say ""
if ($script:Failures -eq 0 -and $script:Warnings -eq 0) {
    Write-Host "  Everything checks out." -ForegroundColor Green
} elseif ($script:Failures -eq 0) {
    Write-Host ("  Ready to run. " + $script:Warnings + " optional item(s) not configured.") -ForegroundColor Yellow
} else {
    Write-Host ("  " + $script:Failures + " blocking problem(s), " +
                $script:Warnings + " optional.") -ForegroundColor Red
}
if ($script:Fixes.Count -gt 0) {
    Say ""
    Say "  Suggested commands:" "Cyan"
    $script:Fixes | ForEach-Object { Say $_ "DarkGray" }
}
Say ""

exit ([int]($script:Failures -gt 0))
