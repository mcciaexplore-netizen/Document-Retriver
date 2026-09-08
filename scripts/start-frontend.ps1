$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'load-env.ps1')
$projectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath (Join-Path $projectPath 'frontend')
if (-not $env:BACKEND_URL) {
    $backendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { '8000' }
    $env:BACKEND_URL = "http://127.0.0.1:$backendPort"
}
$frontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { '3000' }
$env:NEXT_TELEMETRY_DISABLED = '1'
& npm.cmd run dev -- --hostname 127.0.0.1 --port $frontendPort
