param(
    [string]$Cutoff = '2026-10-02T00:00:00+00:00',
    [switch]$WithAirflow
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed: $($args[0])" }
}
Invoke-Docker compose --profile tools build app
Invoke-Docker compose --profile streaming up -d --wait postgres payments kafka
Invoke-Docker compose --profile tools run --rm app bootstrap
Invoke-Docker compose --profile tools run --rm app kafka-produce
Invoke-Docker compose --profile tools run --rm app kafka-consume
Invoke-Docker compose --profile tools run --rm app run --cutoff $Cutoff
Invoke-Docker compose --profile monitoring up -d metrics prometheus
if ($WithAirflow) {
    Invoke-Docker compose --profile orchestration build airflow
    Invoke-Docker compose --profile orchestration up -d airflow
}
$metricsAddress = (Invoke-Docker compose --profile monitoring port metrics 8014).Trim()
$prometheusAddress = (Invoke-Docker compose --profile monitoring port prometheus 9090).Trim()
Write-Output "NusaCommerce pipeline completed. Health: http://$metricsAddress/health"
Write-Output "Prometheus: http://$prometheusAddress"
if ($WithAirflow) {
    $airflowAddress = (Invoke-Docker compose --profile orchestration port airflow 8080).Trim()
    Write-Output "Airflow: http://$airflowAddress"
}
