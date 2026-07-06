Param()
$ErrorActionPreference = 'Stop'

$ListenPort = if ($env:SANMAO_TUNNEL_PORT) { [int]$env:SANMAO_TUNNEL_PORT } else { 13000 }
$PidPath = if ($env:SANMAO_TUNNEL_PID) { $env:SANMAO_TUNNEL_PID } else { Join-Path $HOME '.ssh\sanmao-tunnel.pid' }

function Test-PidRunning($PidValue) {
    if (-not $PidValue) { return $false }
    try {
        Get-Process -Id $PidValue -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

if (Test-Path $PidPath) {
    $pidValue = (Get-Content $PidPath -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (Test-PidRunning $pidValue) {
        Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
        Write-Host "[tunnel] stopped pid=$pidValue"
    }
    Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
}

try {
    Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction Stop |
        ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-Host "[tunnel] removed listener pid=$($_.OwningProcess)"
        }
}
catch {
}
