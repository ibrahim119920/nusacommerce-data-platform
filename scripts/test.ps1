# Run integration checks against a dedicated test database.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if ($env:POSTGRES_PASSWORD -and $env:POSTGRES_PASSWORD -ne 'local-dev-only') {
    throw 'This helper expects the local development password.'
}
$exists = docker compose exec -T postgres psql -U nusa -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='nusacommerce_test'"
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL is not ready' }
if (($exists | Out-String).Trim() -ne '1') {
    docker compose exec -T postgres psql -U nusa -d postgres -c "CREATE DATABASE nusacommerce_test;"
    if ($LASTEXITCODE -ne 0) { throw 'Create test database failed' }
}
$mapping = docker compose port postgres 5432
if ($LASTEXITCODE -ne 0 -or -not $mapping) { throw 'Could not resolve PostgreSQL host port' }
$databasePort = ($mapping.Trim().Split(':')[-1])
$env:POSTGRES_URL = "postgresql+psycopg://nusa:local-dev-only@127.0.0.1:$databasePort/nusacommerce_test"
$env:TEST_POSTGRES_URL = $env:POSTGRES_URL
& ./.venv/Scripts/python.exe -m nusacommerce.cli bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap failed' }
& ./.venv/Scripts/python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
