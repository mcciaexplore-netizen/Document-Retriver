$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'load-env.ps1')
$projectPath = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw 'Run .\scripts\setup.ps1 first to create the local Python environment.'
}
Set-Location -LiteralPath (Join-Path $projectPath 'backend')
& $venvPython -c "import sys; assert sys.version_info >= (3, 12); import fastapi, uvicorn, sqlalchemy, alembic, fitz, openpyxl, pptx, multipart"
if ($LASTEXITCODE -ne 0) {
    throw 'Backend Python or dependencies are unavailable. Run scripts\setup.ps1 from the project root. If Windows Application Control blocks Python, repair setup with -Python pointing to an approved Python 3.12+ installation.'
}
& $venvPython -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
$backendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { '8000' }
& $venvPython -m uvicorn app.main:app --reload --host 127.0.0.1 --port $backendPort
if ($LASTEXITCODE -ne 0) { throw 'Backend stopped with an error. Check the message above, including whether its port is already in use.' }
