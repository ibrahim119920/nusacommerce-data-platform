# Run from the reference repository root. Never target the demo DB for tests.
$ErrorActionPreference = 'Stop'
if ($env:POSTGRES_PASSWORD -and $env:POSTGRES_PASSWORD -ne 'local-reference-only') {
    throw 'This helper expects the default local credential; configure a separate test URL manually.'
}
$exists = docker compose exec -T postgres psql -U nusa -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='nusacommerce_test'"
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL is not ready' }
if (($exists | Out-String).Trim() -ne '1') {
    docker compose exec -T postgres psql -U nusa -d postgres -c "CREATE DATABASE nusacommerce_test;"
    if ($LASTEXITCODE -ne 0) { throw 'Create test database failed' }
}
$env:POSTGRES_URL = 'postgresql+psycopg://nusa:local-reference-only@127.0.0.1:55439/nusacommerce_test'
$env:TEST_POSTGRES_URL = $env:POSTGRES_URL
& ./.venv/Scripts/python.exe -m nusacommerce.cli bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap failed' }
& ./.venv/Scripts/python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
