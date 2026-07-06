Param()
$ErrorActionPreference = 'Stop'

$ListenHost = if ($env:SANMAO_TUNNEL_HOSTNAME) { $env:SANMAO_TUNNEL_HOSTNAME } else { '127.0.0.1' }
$ListenPort = if ($env:SANMAO_TUNNEL_PORT) { [int]$env:SANMAO_TUNNEL_PORT } else { 13000 }
$RemoteHost = if ($env:SANMAO_TUNNEL_HOST) { $env:SANMAO_TUNNEL_HOST } else { 'root@120.24.144.153' }
$RemoteTarget = if ($env:SANMAO_TUNNEL_TARGET) { $env:SANMAO_TUNNEL_TARGET } else { '127.0.0.1:3000' }
$PidPath = if ($env:SANMAO_TUNNEL_PID) { $env:SANMAO_TUNNEL_PID } else { Join-Path $HOME '.ssh\sanmao-tunnel.pid' }
$HealthUrl = if ($env:SANMAO_TUNNEL_HEALTH_URL) { $env:SANMAO_TUNNEL_HEALTH_URL } else { "http://$ListenHost`:$ListenPort/api/status" }

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

function Remove-StalePid {
    if (-not (Test-Path $PidPath)) { return }
    $pidValue = (Get-Content $PidPath -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (Test-PidRunning $pidValue) { return }
    Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
}

function Test-Health {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $HealthUrl -TimeoutSec 3 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Get-ListenerPids {
    try {
        return @(
            Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction Stop |
                Select-Object -ExpandProperty OwningProcess -Unique
        )
    }
    catch {
        return @()
    }
}

Remove-StalePid

if (Test-Path $PidPath) {
    $existingPid = (Get-Content $PidPath -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ((Test-PidRunning $existingPid) -and (Test-Health)) {
        Write-Host "[tunnel] already running: pid=$existingPid"
        Write-Host "[tunnel] health check ok: $HealthUrl"
        exit 0
    }
}

foreach ($listenerPid in Get-ListenerPids) {
    if ($listenerPid) {
        Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
        Write-Host "[tunnel] removed listener pid=$listenerPid"
    }
}

New-Item -ItemType Directory -Force -Path (Split-Path $PidPath -Parent) | Out-Null

$sshArgs = @(
    '-o', 'ExitOnForwardFailure=yes',
    '-o', 'ServerAliveInterval=30',
    '-o', 'ServerAliveCountMax=3',
    '-N',
    '-L', "$ListenHost`:$ListenPort`:$RemoteTarget",
    $RemoteHost
)

Write-Host "[tunnel] opening $ListenHost`:$ListenPort -> $RemoteTarget via $RemoteHost"
$proc = Start-Process -FilePath 'ssh' -ArgumentList $sshArgs -WindowStyle Hidden -PassThru
Set-Content -Path $PidPath -Value $proc.Id -Encoding ASCII

for ($i = 0; $i -lt 5; $i++) {
    if (Test-Health) {
        Write-Host "[tunnel] ready: pid=$($proc.Id)"
        Write-Host "[tunnel] health check ok: $HealthUrl"
        exit 0
    }
    Start-Sleep -Seconds 1
}

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
throw "[tunnel] failed health check: $HealthUrl"
