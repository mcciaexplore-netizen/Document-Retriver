[CmdletBinding()]
param([string]$Python = 'python')

$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectPath

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'Node.js 22 LTS or later is required. Install Node.js, then run this script again.'
}
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}

$venvPython = Join-Path $projectPath '.venv\Scripts\python.exe'
$localUv = Join-Path $projectPath '.tools\uv.exe'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectPath '.tools\python'
$env:UV_CACHE_DIR = Join-Path $projectPath '.tools\cache'
$env:PIP_CACHE_DIR = Join-Path $projectPath '.tools\pip-cache'
$env:npm_config_cache = Join-Path $projectPath '.tools\npm-cache'
if ($PSBoundParameters.ContainsKey('Python')) {
    # Refresh an existing environment as well, so an approved replacement runtime
    # can repair a broken interpreter without deleting installed project files.
    & $Python -c "import sys; assert sys.version_info >= (3, 12), 'Python 3.12 or later is required'"
    if ($LASTEXITCODE -ne 0) { throw 'The selected Python cannot run. Choose an installed runtime permitted by Windows Application Control.' }
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not repair the Python environment with the selected runtime.' }
} elseif (-not (Test-Path -LiteralPath $venvPython)) {
    if ((Test-Path -LiteralPath $localUv) -and $Python -eq 'python') {
        & $localUv venv --python 3.12 .venv
    } else {
        & $Python -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment. Pass -Python with the path to Python 3.12 or later.' }
}
& $venvPython -c "import sys; assert sys.version_info >= (3, 12)"
if ($LASTEXITCODE -ne 0) {
    throw 'The project Python cannot run. If Windows Application Control blocks it, use an approved Python installation, then run .\scripts\setup.ps1 -Python C:\path\to\python.exe.'
}
if (Test-Path -LiteralPath $localUv) {
    & $localUv pip install --python $venvPython -r backend/requirements.txt
} else {
    & $venvPython -m pip install -r backend/requirements.txt
}
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
& npm.cmd --prefix frontend ci
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }

Write-Host ''
Write-Host 'Setup complete. Open two terminals in Doc-retriver:'
Write-Host '  .\scripts\start-backend.ps1'
Write-Host '  .\scripts\start-frontend.ps1'
Write-Host 'Then open http://localhost:3000'
