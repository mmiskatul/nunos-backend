# start.ps1 — Start Nunos Backend accessible from all network interfaces
# This allows phones and other devices on the same Wi-Fi to connect.
#
# Usage: .\start.ps1
# Or with a custom port: .\start.ps1 -Port 9000

param(
    [int]$Port = 8000,
    [string]$Host = "0.0.0.0"
)

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  Nunos Backend" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# Show your PC's LAN IPs so you know what to put in nuno/.env
Write-Host "Your PC's IP addresses (for phone testing):" -ForegroundColor Yellow
$ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.*" }
foreach ($ip in $ips) {
    Write-Host "  http://$($ip.IPAddress):$Port" -ForegroundColor Green
}
Write-Host ""
Write-Host "Backend starting at: http://${Host}:${Port}" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""

# Activate virtual environment if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & ".venv\Scripts\Activate.ps1"
    Write-Host "Virtual environment activated." -ForegroundColor Gray
}

# Start uvicorn bound to all interfaces
uvicorn app.main:app --host $Host --port $Port --reload
