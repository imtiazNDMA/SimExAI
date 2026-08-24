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

.PARAMETER BindHost
    Address the backend listens on. Default 0.0.0.0, which accepts connections
    from other machines on the same network. Use 127.0.0.1 to restrict access
    to this machine only.

.PARAMETER NoSync
    Skip 'uv sync'. Use for fast restarts when dependencies haven't changed.

.PARAMETER NoBrowser
    Don't open the browser.

.PARAMETER Https
    Serve the app over HTTPS. Required for microphone access from LAN clients.
    Uses .certs/simexai-server.cert.pem and .certs/simexai-server.key.pem unless
    explicit certificate paths are provided.

.PARAMETER SslCertFile
    PEM server certificate path. Supplying it enables HTTPS.

.PARAMETER SslKeyFile
    PEM private-key path. Supplying it enables HTTPS.

.EXAMPLE
    .\start.ps1
.EXAMPLE
    .\start.ps1 -Port 8080 -NoSync
.EXAMPLE
    # Local-only, not reachable from the network
    .\start.ps1 -BindHost 127.0.0.1
.EXAMPLE
    # First run: .\scripts\setup_https.ps1 -TrustLocal
    .\start.ps1 -Https
#>
[CmdletBinding()]
param(
    [int]$Port = 9897,
    [string]$BindHost = '0.0.0.0',
    [switch]$NoSync,
    [switch]$NoBrowser,
    [switch]$Https,
    [string]$SslCertFile,
    [string]$SslKeyFile
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

# ── 6. HTTPS configuration ──────────────────────────────────
$useHttps = $Https -or $SslCertFile -or $SslKeyFile
if ($useHttps) {
    if (-not $SslCertFile) {
        $SslCertFile = Join-Path $root '.certs\simexai-server.cert.pem'
    }
    if (-not $SslKeyFile) {
        $SslKeyFile = Join-Path $root '.certs\simexai-server.key.pem'
    }
    if (-not (Test-Path -LiteralPath $SslCertFile)) {
        Write-Err "HTTPS certificate not found: $SslCertFile"
        Write-Host "    Generate one with: .\scripts\setup_https.ps1 -TrustLocal"
        exit 1
    }
    if (-not (Test-Path -LiteralPath $SslKeyFile)) {
        Write-Err "HTTPS private key not found: $SslKeyFile"
        Write-Host "    Generate one with: .\scripts\setup_https.ps1 -TrustLocal"
        exit 1
    }
    $SslCertFile = (Resolve-Path -LiteralPath $SslCertFile).Path
    $SslKeyFile = (Resolve-Path -LiteralPath $SslKeyFile).Path
    Write-Ok "HTTPS enabled"
} elseif ($BindHost -eq '0.0.0.0') {
    Write-Warn "LAN clients will not have microphone access over HTTP. Use -Https for voice input."
}

# ── 7. Browser opener (background) ──────────────────────────
# Always open the local URL -- 0.0.0.0 is a bind address, not something a
# browser can navigate to.
$appUrl = if ($useHttps) { "https://localhost:$Port" } else { "http://localhost:$Port" }
$urlScheme = if ($useHttps) { 'https' } else { 'http' }

# When listening on all interfaces, work out the addresses other machines use.
# The interface name is shown alongside each one because this box also has
# virtual adapters (WSL/Hyper-V switches, Tailscale) whose addresses are not
# the LAN address colleagues need.
$lanUrls = @()
if ($BindHost -eq '0.0.0.0') {
    $lanUrls = @(
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object {
                $_.IPAddress -ne '127.0.0.1' -and
                $_.PrefixOrigin -in @('Dhcp', 'Manual') -and
                $_.IPAddress -notlike '169.254.*'
            } |
            Sort-Object IPAddress -Unique |
            ForEach-Object {
                [PSCustomObject]@{
                    Url       = "$urlScheme`://$($_.IPAddress):$Port"
                    Interface = $_.InterfaceAlias
                }
            }
    )
}

if (-not $NoBrowser) {
    Start-Job -Name 'simexai-browser' -ScriptBlock {
        param($url)
        # Poll until the server answers, then open once. Give up after ~60s.
        $uri = [Uri]$url
        for ($i = 0; $i -lt 120; $i++) {
            Start-Sleep -Milliseconds 500
            try {
                # Windows PowerShell 5.1 can reject a trusted private CA when
                # it has no online revocation server. For HTTPS, a successful
                # TCP connection is enough before handing the URL to the browser.
                if ($uri.Scheme -eq 'https') {
                    $client = New-Object System.Net.Sockets.TcpClient
                    try {
                        $pending = $client.BeginConnect($uri.Host, $uri.Port, $null, $null)
                        if ($pending.AsyncWaitHandle.WaitOne(2000)) {
                            $client.EndConnect($pending)
                            Start-Process $url
                            return
                        }
                    } finally {
                        $client.Close()
                    }
                    continue
                }
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

# ── 8. Launch ───────────────────────────────────────────────
Write-Step "Starting SimEx AI on $appUrl"
if ($BindHost -eq '0.0.0.0') {
    if ($lanUrls) {
        Write-Ok "Reachable from other machines at:"
        $pad = ($lanUrls | ForEach-Object { $_.Url.Length } | Measure-Object -Maximum).Maximum
        foreach ($u in $lanUrls) {
            Write-Host ("      {0}  " -f $u.Url.PadRight($pad)) -ForegroundColor Green -NoNewline
            Write-Host "($($u.Interface))" -ForegroundColor DarkGray
        }
    } else {
        Write-Warn "Listening on all interfaces, but no network address was found."
    }
    Write-Warn "Windows Firewall may prompt to allow access -- choose the private network."
} else {
    Write-Ok "Bound to $BindHost (this machine only)"
}
Write-Host "    Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

try {
    $uvicornArgs = @(
        'run', 'uvicorn', 'backend.app:app', '--reload',
        '--host', $BindHost, '--port', $Port
    )
    if ($useHttps) {
        $uvicornArgs += @("--ssl-certfile", $SslCertFile, "--ssl-keyfile", $SslKeyFile)
    }
    & uv @uvicornArgs
} finally {
    # Clean up the browser job whether we exited normally or via Ctrl+C.
    Get-Job -Name 'simexai-browser' -ErrorAction SilentlyContinue |
        Remove-Job -Force -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host "SimEx AI stopped." -ForegroundColor DarkGray
}
