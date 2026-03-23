Param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"

Write-Host "Starting School Risk stack..." -ForegroundColor Cyan

if ($Build) {
    docker compose up -d --build
} else {
    docker compose up -d
}

Write-Host ""
Write-Host "Core endpoints:" -ForegroundColor Green
Write-Host "  Web UI:        http://localhost"
Write-Host "  Risk Engine:   http://localhost:8001/health"
Write-Host "  Clip Service:  http://localhost:8002/health"
Write-Host "  Stream Server: http://localhost:8003/api/cameras"
Write-Host ""
Write-Host "Tail logs (optional): docker compose logs -f" -ForegroundColor Yellow
