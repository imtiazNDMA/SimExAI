<#
.SYNOPSIS
    Generate a local CA and HTTPS server certificate for SimEx AI.

.DESCRIPTION
    Creates PEM files for Uvicorn with SANs for localhost, an optional DNS name,
    and the current machine's LAN IPv4 addresses. The CA is trusted for the
    current Windows user only when -TrustLocal is explicitly supplied.

    Participant machines must trust simexai-ca.cert.pem before opening an HTTPS
    LAN URL. Never copy either *.key.pem file to participant machines.
#>
[CmdletBinding()]
param(
    [string]$OutputDir,
    [string]$DnsName = 'simexai.local',
    [string[]]$IpAddress = @(),
    [int]$ValidDays = 825,
    [switch]$TrustLocal,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
if (-not $OutputDir) {
    $OutputDir = Join-Path $PSScriptRoot '..\.certs'
}
$openssl = Get-Command openssl -ErrorAction SilentlyContinue
if (-not $openssl) {
    Write-Error "OpenSSL is required. Install it or place 'openssl' on PATH, then retry."
    exit 1
}

if (-not [System.IO.Path]::IsPathRooted($OutputDir)) {
    $OutputDir = Join-Path (Get-Location) $OutputDir
}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path

$caKey = Join-Path $OutputDir 'simexai-ca.key.pem'
$caCert = Join-Path $OutputDir 'simexai-ca.cert.pem'
$serverKey = Join-Path $OutputDir 'simexai-server.key.pem'
$serverCsr = Join-Path $OutputDir 'simexai-server.csr.pem'
$serverCert = Join-Path $OutputDir 'simexai-server.cert.pem'
$sanConfig = Join-Path $OutputDir 'simexai-server-san.cnf'
$serialFile = Join-Path $OutputDir 'simexai-ca.cert.srl'

$generatedFiles = @($caKey, $caCert, $serverKey, $serverCsr, $serverCert, $sanConfig, $serialFile)
if (-not $Force -and ($generatedFiles | Where-Object { Test-Path -LiteralPath $_ })) {
    Write-Error "Certificate files already exist in '$OutputDir'. Use -Force to regenerate them."
    exit 1
}
if ($Force) {
    $generatedFiles | ForEach-Object {
        Remove-Item -LiteralPath $_ -Force -ErrorAction SilentlyContinue
    }
}

if (-not $IpAddress -or $IpAddress.Count -eq 0) {
    $IpAddress = @(
        '127.0.0.1'
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object {
                $_.IPAddress -ne '127.0.0.1' -and
                $_.IPAddress -notlike '169.254.*' -and
                $_.PrefixOrigin -in @('Dhcp', 'Manual')
            } |
            Select-Object -ExpandProperty IPAddress -Unique
    )
}
$IpAddress = @($IpAddress | Where-Object { $_ } | Sort-Object -Unique)

$dnsNames = @('localhost')
if ($DnsName -and $DnsName -ne 'localhost') { $dnsNames += $DnsName }
$dnsNames = @($dnsNames | Sort-Object -Unique)

$configLines = @(
    '[req]',
    'distinguished_name = req_distinguished_name',
    'prompt = no',
    '',
    '[req_distinguished_name]',
    "CN = $DnsName",
    '',
    '[v3_req]',
    'basicConstraints = critical,CA:FALSE',
    'keyUsage = critical,digitalSignature,keyEncipherment',
    'extendedKeyUsage = serverAuth',
    'subjectAltName = @alt_names',
    '',
    '[alt_names]'
)
for ($i = 0; $i -lt $dnsNames.Count; $i++) {
    $configLines += "DNS.$($i + 1) = $($dnsNames[$i])"
}
for ($i = 0; $i -lt $IpAddress.Count; $i++) {
    $configLines += "IP.$($i + 1) = $($IpAddress[$i])"
}
Set-Content -LiteralPath $sanConfig -Value $configLines -Encoding Ascii

function Invoke-OpenSsl {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & $openssl.Source @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "OpenSSL failed with exit code ${LASTEXITCODE}: openssl $($Arguments -join ' ')"
    }
}

Write-Host 'Generating SimEx AI local certificate authority...' -ForegroundColor Cyan
Invoke-OpenSsl -Arguments @(
    'req', '-x509', '-newkey', 'rsa:3072', '-nodes', '-sha256',
    '-keyout', $caKey, '-out', $caCert, '-days', '3650',
    '-subj', '/CN=SimExAI Local Development CA', '-config', $sanConfig
)

Write-Host 'Generating HTTPS server certificate...' -ForegroundColor Cyan
Invoke-OpenSsl -Arguments @(
    'req', '-newkey', 'rsa:2048', '-nodes', '-sha256',
    '-keyout', $serverKey, '-out', $serverCsr, '-subj', "/CN=$DnsName",
    '-config', $sanConfig
)
Invoke-OpenSsl -Arguments @(
    'x509', '-req', '-sha256', '-in', $serverCsr,
    '-CA', $caCert, '-CAkey', $caKey, '-CAcreateserial',
    '-out', $serverCert, '-days', [string]$ValidDays,
    '-extfile', $sanConfig, '-extensions', 'v3_req'
)
Remove-Item -LiteralPath $serverCsr -Force -ErrorAction SilentlyContinue

if ($TrustLocal) {
    Write-Host 'Trusting the SimEx AI CA for the current Windows user...' -ForegroundColor Cyan
    & certutil -user -addstore Root $caCert | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "certutil failed to trust '$caCert'."
    }
}

Write-Host ''
Write-Host 'HTTPS certificate created.' -ForegroundColor Green
Write-Host "  Server certificate: $serverCert"
Write-Host "  Server private key: $serverKey"
Write-Host "  Client trust certificate: $caCert"
Write-Host ''
if (-not $TrustLocal) {
    Write-Host 'Trust the CA on this machine with:' -ForegroundColor Yellow
    Write-Host "  certutil -user -addstore Root `"$caCert`""
}
Write-Host 'On each participant machine, copy only simexai-ca.cert.pem and run:' -ForegroundColor Yellow
Write-Host '  certutil -user -addstore Root .\simexai-ca.cert.pem'
Write-Host 'Then launch SimEx AI with: start.bat -Https'
