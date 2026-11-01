param([string]$Python = ".venv/Scripts/python.exe")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath $Python)) { throw "Create the Python environment first; see README.md. Or supply -Python with an existing compatible interpreter." }
$env:PYTHONPATH = Join-Path $projectRoot "services/api"
& $Python scripts/init-local.py
if ($LASTEXITCODE -ne 0) { throw "Local configuration failed" }
& $Python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Database migration failed" }
& $Python -m uranium.seed
if ($LASTEXITCODE -ne 0) { throw "Seed failed" }
& $Python scripts/init-phase4.py
if ($LASTEXITCODE -ne 0) { throw "Review examples failed" }
& $Python scripts/init-phase5.py
if ($LASTEXITCODE -ne 0) { throw "Evidence examples failed" }
& $Python scripts/seed-portal-content.py
if ($LASTEXITCODE -ne 0) { throw "Notice setup failed" }
& $Python scripts/seed-demo-accounts.py
if ($LASTEXITCODE -ne 0) { throw "Sample sign-in setup failed" }
& $Python scripts/seed-restored-portal.py
if ($LASTEXITCODE -ne 0) { throw "Institution and application examples failed" }
Write-Output "Setup complete. The three sample buttons fill usable credentials. Other account passwords remain in the private .env file. Start the services as described in README.md."
