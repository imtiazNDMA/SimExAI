<#
.SYNOPSIS
    One-command dev launcher for SimEx AI.

.DESCRIPTION
    Verifies prerequisites, syncs dependencies, checks that the configured LLM
    server is reachable, starts the FastAPI backend, and opens the browser once
    the server answers.

    Normally invoked via start.bat.

.PARAMETER Port
    Port for the backend. Default 9897.

.PARAMETER NoSync
    Skip 'uv sync'. Use for fast restarts when dependencies haven't changed.

.PARAMETER NoBrowser
    Don't open the browser.

.EXAMPLE
    .\start.ps1
.EXAMPLE
    .\start.ps1 -Port 8080 -NoSync
#>
[CmdletBinding()]
param(
    [int]$Port = 9897,
    [switch]$NoSync,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root

function Write-Step { param($m) Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Ok   { param($m) Write-Host "    $m" -ForegroundColor Green }
function Write-Warn { param($m) Write-Host "    $m" -ForegroundColor Yellow }
function Write-Err  { param($m) Write-Host "!!! $m" -ForegroundColor Red }

# ── 1. Prerequisites ────────────────────────────────────────
Write-Step "Checking prerequisites"

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Err "'uv' is not on PATH."
    Write-Host "    Install it from https://docs.astral.sh/uv/getting-started/installation/"
    Write-Host "    then re-run this script."
    exit 1
}
Write-Ok "uv found: $($uv.Source)"

# ── 2. Environment file ─────────────────────────────────────
Write-Step "Checking .env"

$envPath = Join-Path $root '.env'
$envExamplePath = Join-Path $root '.env.example'

if (-not (Test-Path $envPath)) {
    if (Test-Path $envExamplePath) {
        Copy-Item $envExamplePath $envPath
        Write-Err "No .env found - created one from .env.example."
        Write-Host "    Fill in PINECONE_API_KEY (and check the LLM settings), then re-run."
    } else {
        Write-Err "No .env and no .env.example to copy from."
    }
    exit 1
}

# Parse .env into a hashtable (KEY=VALUE, ignoring comments and blanks).
$envVars = @{}
foreach ($line in (Get-Content $envPath)) {
    $trimmed = $line.Trim()
    if ($trimmed -eq '' -or $trimmed.StartsWith('#')) { continue }
    $idx = $trimmed.IndexOf('=')
    if ($idx -lt 1) { continue }
    $key = $trimmed.Substring(0, $idx).Trim()
    $val = $trimmed.Substring($idx + 1).Trim().Trim('"').Trim("'")
    $envVars[$key] = $val
}
Write-Ok ".env loaded ($($envVars.Count) settings)"

if (-not $envVars['PINECONE_API_KEY'] -or $envVars['PINECONE_API_KEY'] -like '*your_pinecone*') {
    Write-Warn "PINECONE_API_KEY looks unset - RAG retrieval will be disabled."
}

# ── 3. Dependencies ─────────────────────────────────────────
if ($NoSync) {
    Write-Step "Skipping dependency sync (-NoSync)"
} else {
    Write-Step "Syncing dependencies"
    & uv sync
    if ($LASTEXITCODE -ne 0) {
        Write-Err "'uv sync' failed (exit $LASTEXITCODE)."
        exit 1
    }
    Write-Ok "Dependencies up to date"
}

# ── 4. LLM server preflight ─────────────────────────────────
# Provider-agnostic: prefers LM Studio settings when present, falls back to
# Ollama, so this keeps working across the pending provider migration.
Write-Step "Checking LLM server"

if ($envVars['LMSTUDIO_BASE_URL']) {
    $llmName  = 'LM Studio'
    $llmBase  = $envVars['LMSTUDIO_BASE_URL'].TrimEnd('/')
    $llmModel = $envVars['LMSTUDIO_MODEL']
    $llmProbe = "$llmBase/models"
} else {
    $llmName  = 'Ollama'
    if ($envVars['OLLAMA_BASE_URL']) {
        $llmBase = $envVars['OLLAMA_BASE_URL'].TrimEnd('/')
    } else {
        $llmBase = 'http://localhost:11434'
    }
    $llmModel = $envVars['OLLAMA_MODEL']
    $llmProbe = "$llmBase/api/tags"
}

Write-Host "    Provider: $llmName"
Write-Host "    Base URL: $llmBase"
if ($llmModel) { Write-Host "    Model:    $llmModel" }

$llmUp = $false
try {
    $resp = Invoke-WebRequest -Uri $llmProbe -TimeoutSec 5 -UseBasicParsing
    if ($resp.StatusCode -eq 200) { $llmUp = $true }
} catch {
    $llmUp = $false
}

if ($llmUp) {
    Write-Ok "$llmName is reachable"
    if ($llmModel -and $resp.Content -notlike "*$llmModel*") {
        Write-Warn "Model '$llmModel' was not listed by the server - it may not be loaded."
    }
} else {
    Write-Warn "$llmName is NOT reachable at $llmBase"
    Write-Warn "The app will start, but chat will fail until the server is running."
}

# ── 5. Port availability ────────────────────────────────────
Write-Step "Checking port $Port"

$portBusy = $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
if ($portBusy) {
    Write-Err "Port $Port is already in use."
    Write-Host "    Stop the process using it, or run: .\start.ps1 -Port 9898"
    exit 1
}
Write-Ok "Port $Port is free"

# ── 6. Browser opener (background) ──────────────────────────
$appUrl = "http://localhost:$Port"

if (-not $NoBrowser) {
    Start-Job -Name 'simexai-browser' -ScriptBlock {
        param($url)
        # Poll until the server answers, then open once. Give up after ~60s.
        for ($i = 0; $i -lt 120; $i++) {
            Start-Sleep -Milliseconds 500
            try {
                $r = Invoke-WebRequest -Uri $url -TimeoutSec 2 -UseBasicParsing
                if ($r.StatusCode -eq 200) {
                    Start-Process $url
                    return
                }
            } catch {
                # server not up yet - keep waiting
            }
        }
    } -ArgumentList $appUrl | Out-Null
}

# ── 7. Launch ───────────────────────────────────────────────
Write-Step "Starting SimEx AI on $appUrl"
Write-Host "    Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

try {
    & uv run uvicorn backend.app:app --reload --port $Port
} finally {
    # Clean up the browser job whether we exited normally or via Ctrl+C.
    Get-Job -Name 'simexai-browser' -ErrorAction SilentlyContinue |
        Remove-Job -Force -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host "SimEx AI stopped." -ForegroundColor DarkGray
}
