Param(
    [string]$InstallBinDir = "$HOME\AppData\Local\smclaude\bin",
    [string]$InstallConfigDir = "$HOME\AppData\Local\smclaude\config",
    [switch]$SkipPathHint
)

$ErrorActionPreference = 'Stop'

$installBin = Join-Path $InstallBinDir 'claude-sanmao.ps1'
$tunnelStart = Join-Path $InstallConfigDir 'start-local-tunnel.ps1'
$tunnelStop = Join-Path $InstallConfigDir 'stop-local-tunnel.ps1'
$smclaude = Join-Path $InstallBinDir 'smclaude.ps1'
$smclaudeCmd = Join-Path $InstallBinDir 'smclaude.cmd'
$smclaudeModels = Join-Path $InstallBinDir 'smclaude-models.ps1'
$smclaudeModelsCmd = Join-Path $InstallBinDir 'smclaude-models.cmd'
$smclaudePick = Join-Path $InstallBinDir 'smclaude-pick.ps1'
$smclaudePickCmd = Join-Path $InstallBinDir 'smclaude-pick.cmd'
$smclaudeSetup = Join-Path $InstallBinDir 'smclaude-setup.ps1'
$smclaudeSetupCmd = Join-Path $InstallBinDir 'smclaude-setup.cmd'

New-Item -ItemType Directory -Force -Path $InstallBinDir | Out-Null
New-Item -ItemType Directory -Force -Path $InstallConfigDir | Out-Null

@'
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

function Remove-StalePid() {
    if (-not (Test-Path $PidPath)) { return }
    $pidValue = (Get-Content $PidPath -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (Test-PidRunning $pidValue) { return }
    Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
}

function Test-Health() {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $HealthUrl -TimeoutSec 3 | Out-Null
        return $true
    }
    catch {
        return $false
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
Set-Content -Path $PidPath -Value $proc.Id

for ($i = 0; $i -lt 5; $i++) {
    if (Test-Health) {
        Write-Host "[tunnel] ready: pid=$($proc.Id)"
        Write-Host "[tunnel] health check ok: $HealthUrl"
        exit 0
    }
    Start-Sleep -Seconds 1
}

throw "[tunnel] failed health check: $HealthUrl"
'@ | Set-Content -Path $tunnelStart -Encoding UTF8

@'
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

Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Host "[tunnel] removed listener pid=$($_.OwningProcess)"
    }
'@ | Set-Content -Path $tunnelStop -Encoding UTF8

@'
Param(
    [switch]$PrintEnv,
    [switch]$SkipTunnel,
    [switch]$ListModels,
    [switch]$PickModel,
    [switch]$SessionOnly,
    [switch]$ClearDefaultModel,
    [switch]$Setup,
    [string]$Model,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ClaudeArgs
)

$ErrorActionPreference = 'Stop'

$ConfigDir = if ($env:SANMAO_CLAUDE_CONFIG_DIR) { $env:SANMAO_CLAUDE_CONFIG_DIR } else { Join-Path $HOME 'AppData\Local\smclaude\config' }
$TunnelStart = if ($env:SANMAO_START_TUNNEL_SCRIPT) { $env:SANMAO_START_TUNNEL_SCRIPT } else { Join-Path $ConfigDir 'start-local-tunnel.ps1' }
$BaseUrl = if ($env:SANMAO_CLAUDE_BASE_URL) { $env:SANMAO_CLAUDE_BASE_URL } else { 'http://127.0.0.1:13000' }
$ModelsUrl = if ($env:SANMAO_CLAUDE_MODELS_URL) { $env:SANMAO_CLAUDE_MODELS_URL } else { "$BaseUrl/v1/models" }
$StateDir = if ($env:SANMAO_CLAUDE_STATE_DIR) { $env:SANMAO_CLAUDE_STATE_DIR } else { Join-Path $HOME '.config\sanmao-claude' }
$DefaultModelFile = Join-Path $StateDir 'default-model'
$ConfigFile = Join-Path $StateDir 'config.ps1env'
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

function Load-ConfigToken {
    if (Test-Path $ConfigFile) {
        foreach ($line in Get-Content $ConfigFile) {
            if ($line -match '^\$env:SANMAO_API_KEY=\"(.+)\"$') {
                return $Matches[1]
            }
        }
    }
    return $null
}

function Save-ConfigToken($Token) {
    Set-Content -Path $ConfigFile -Value "`$env:SANMAO_API_KEY=\"$Token\"" -Encoding UTF8
}

function Ensure-Tunnel {
    if (-not $SkipTunnel) {
        if (-not (Test-Path $TunnelStart)) {
            throw "[claude-sanmao] missing tunnel helper at $TunnelStart"
        }
        powershell -ExecutionPolicy Bypass -File $TunnelStart | Out-Null
    }
}

$token = $env:SANMAO_API_KEY
if (-not $token) { $token = $env:ANTHROPIC_API_KEY_SM }
if (-not $token) { $token = $env:ANTHROPIC_AUTH_TOKEN_SM }
if (-not $token) { $token = $env:ANTHROPIC_API_KEY }
if (-not $token) { $token = Load-ConfigToken }

if ($Setup) {
    if (-not $token) {
        $secure = Read-Host 'Enter sanmao API key'
        $token = $secure
    }
    if (-not $token) {
        throw '[claude-sanmao] no API key provided'
    }
    Save-ConfigToken $token
    Write-Host "[claude-sanmao] saved token to $ConfigFile"
    exit 0
}

if (-not $token) {
    throw "[claude-sanmao] missing SANMAO_API_KEY, ANTHROPIC_API_KEY_SM, or stored config at $ConfigFile"
}

$env:ANTHROPIC_API_KEY = $token
$env:ANTHROPIC_BASE_URL = $BaseUrl
Remove-Item Env:ANTHROPIC_AUTH_TOKEN -ErrorAction SilentlyContinue

function Fetch-Models {
    $headers = @{
        'x-api-key' = $env:ANTHROPIC_API_KEY
        'anthropic-version' = '2023-06-01'
    }
    $priority = @(
        'glm-5.2','glm-5.1','glm-5',
        'qwen3.7-max','qwen3.7-plus',
        'deepseek-v4-pro','deepseek-v4-flash',
        'claude-opus-4-8','claude-opus-4-7','claude-opus-4-6',
        'claude-sonnet-4-6','claude-sonnet-4-5-20250929','claude-haiku-4-5-20251001',
        'gpt-5.5','gpt-5.4','gpt-5.4-mini','gpt-5.3-codex-spark','codex-auto-review'
    )
    $payload = Invoke-RestMethod -Method Get -Headers $headers -Uri $ModelsUrl
    $ids = @($payload.data | ForEach-Object { $_.id })
    $ordered = @($priority | Where-Object { $ids -contains $_ })
    $remaining = @($ids | Where-Object { $ordered -notcontains $_ } | Sort-Object)
    return @($ordered + $remaining)
}

function Pick-Model($CurrentModel) {
    $models = Fetch-Models
    if (-not $models -or $models.Count -eq 0) {
        throw '[claude-sanmao] no models available from sanmao'
    }
    Write-Host 'Available sanmao-backed Claude models:'
    for ($i = 0; $i -lt $models.Count; $i++) {
        $marker = if ($CurrentModel -and $models[$i] -eq $CurrentModel) { ' *' } else { '  ' }
        '{0,2}.{1} {2}' -f ($i + 1), $marker, $models[$i] | Write-Host
    }
    Write-Host ''
    $choice = Read-Host 'Model'
    if (-not $choice) {
        throw '[claude-sanmao] model selection cancelled'
    }
    if ($choice -match '^[0-9]+$') {
        $index = [int]$choice - 1
        if ($index -ge 0 -and $index -lt $models.Count) {
            return $models[$index]
        }
        throw '[claude-sanmao] invalid selection'
    }
    if ($models -contains $choice) {
        return $choice
    }
    $matches = @($models | Where-Object { $_.ToLower().Contains($choice.ToLower()) })
    if ($matches.Count -eq 1) {
        return $matches[0]
    }
    if ($matches.Count -gt 1) {
        throw ('[claude-sanmao] ambiguous match: ' + ($matches -join ', '))
    }
    throw '[claude-sanmao] model not found'
}

if ($ClearDefaultModel -and (Test-Path $DefaultModelFile)) {
    Remove-Item $DefaultModelFile -Force
}

if ($PrintEnv) {
    Ensure-Tunnel
    Write-Host "ANTHROPIC_BASE_URL=$BaseUrl"
    Write-Host 'ANTHROPIC_API_KEY is set'
    Write-Host 'ANTHROPIC_AUTH_TOKEN is unset'
    if (Test-Path $DefaultModelFile) {
        Write-Host ("DEFAULT_MODEL=" + (Get-Content $DefaultModelFile -ErrorAction SilentlyContinue | Select-Object -First 1))
    }
    else {
        Write-Host 'DEFAULT_MODEL is not set'
    }
    Write-Host "CONFIG_FILE=$ConfigFile"
    exit 0
}

Ensure-Tunnel

if ($ListModels) {
    Fetch-Models | ForEach-Object { Write-Host $_ }
    exit 0
}

$currentDefault = $null
if (Test-Path $DefaultModelFile) {
    $currentDefault = Get-Content $DefaultModelFile -ErrorAction SilentlyContinue | Select-Object -First 1
}

if (-not $Model -and -not $PickModel -and (-not $ClaudeArgs -or $ClaudeArgs.Count -eq 0) -and -not $currentDefault) {
    $PickModel = $true
}

$selectedModel = $Model
if ($PickModel) {
    $selectedModel = Pick-Model $currentDefault
} elseif (-not $selectedModel -and $currentDefault) {
    $selectedModel = $currentDefault
}

if ($selectedModel -and -not $SessionOnly) {
    Set-Content -Path $DefaultModelFile -Value $selectedModel -Encoding UTF8
}

$claudeCmd = Get-Command claude -ErrorAction Stop
if ($selectedModel) {
    if ($ClaudeArgs -and $ClaudeArgs.Count -gt 0) {
        & $claudeCmd.Source --model $selectedModel @ClaudeArgs
    } else {
        & $claudeCmd.Source --model $selectedModel
    }
    exit $LASTEXITCODE
}

if ($ClaudeArgs -and $ClaudeArgs.Count -gt 0) {
    & $claudeCmd.Source @ClaudeArgs
} else {
    & $claudeCmd.Source
}
exit $LASTEXITCODE
'@ | Set-Content -Path $installBin -Encoding UTF8

@'
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ArgsFromCmd)
if ($ArgsFromCmd.Count -eq 0) {
  & "$HOME\AppData\Local\smclaude\bin\claude-sanmao.ps1" pick
} else {
  & "$HOME\AppData\Local\smclaude\bin\claude-sanmao.ps1" @ArgsFromCmd
}
exit $LASTEXITCODE
'@ | Set-Content -Path $smclaude -Encoding UTF8

@'
@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0smclaude.ps1" %*
'@ | Set-Content -Path $smclaudeCmd -Encoding ASCII

@'
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ArgsFromCmd)
& "$HOME\AppData\Local\smclaude\bin\claude-sanmao.ps1" models @ArgsFromCmd
exit $LASTEXITCODE
'@ | Set-Content -Path $smclaudeModels -Encoding UTF8

@'
@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0smclaude-models.ps1" %*
'@ | Set-Content -Path $smclaudeModelsCmd -Encoding ASCII

@'
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ArgsFromCmd)
& "$HOME\AppData\Local\smclaude\bin\claude-sanmao.ps1" pick @ArgsFromCmd
exit $LASTEXITCODE
'@ | Set-Content -Path $smclaudePick -Encoding UTF8

@'
@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0smclaude-pick.ps1" %*
'@ | Set-Content -Path $smclaudePickCmd -Encoding ASCII

@'
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ArgsFromCmd)
& "$HOME\AppData\Local\smclaude\bin\claude-sanmao.ps1" setup @ArgsFromCmd
exit $LASTEXITCODE
'@ | Set-Content -Path $smclaudeSetup -Encoding UTF8

@'
@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0smclaude-setup.ps1" %*
'@ | Set-Content -Path $smclaudeSetupCmd -Encoding ASCII

Write-Host "[smclaude-install] installed launchers into $InstallBinDir"
Write-Host "[smclaude-install] config dir: $InstallConfigDir"
if (-not $SkipPathHint) {
    Write-Host ''
    Write-Host 'If these commands are not found in a new terminal, add this user bin directory to PATH:'
    Write-Host "  $InstallBinDir"
    Write-Host 'Then open a new PowerShell window.'
}
Write-Host '[smclaude-install] next steps:'
Write-Host "  1. $InstallBinDir\smclaude-setup.cmd"
Write-Host "  2. $InstallBinDir\smclaude-models.cmd"
Write-Host "  3. $InstallBinDir\smclaude.cmd or $InstallBinDir\smclaude-pick.cmd"
