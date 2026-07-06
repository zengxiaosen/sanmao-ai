Param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = 'Stop'

$PrintEnv = $false
$SkipTunnel = $false
$ListModels = $false
$PickModel = $false
$SessionOnly = $false
$ClearDefault = $false
$Setup = $false
$RememberModel = $false
$Model = $null
$ClaudeArgs = @()

$i = 0
$stopParsing = $false
while ($i -lt $Args.Count) {
    if ($stopParsing) {
        $ClaudeArgs += $Args[$i]
        $i++
        continue
    }

    $arg = $Args[$i]
    switch ($arg) {
        'models' { $ListModels = $true; $i++; continue }
        'pick' { $PickModel = $true; $i++; continue }
        'setup' { $Setup = $true; $i++; continue }
        'clear-default' { $ClearDefault = $true; $i++; continue }
        '--print-env' { $PrintEnv = $true; $i++; continue }
        '--skip-tunnel' { $SkipTunnel = $true; $i++; continue }
        '--list-models' { $ListModels = $true; $i++; continue }
        '--pick-model' { $PickModel = $true; $i++; continue }
        '--session-only' { $SessionOnly = $true; $i++; continue }
        '--clear-default-model' { $ClearDefault = $true; $i++; continue }
        '--remember-model' { $RememberModel = $true; $i++; continue }
        '--setup' { $Setup = $true; $i++; continue }
        '--model' {
            if (($i + 1) -ge $Args.Count) {
                throw '[smagent] --model requires a value'
            }
            $Model = $Args[$i + 1]
            $i += 2
            continue
        }
        '--' {
            $stopParsing = $true
            $i++
            continue
        }
        default {
            $stopParsing = $true
            continue
        }
    }
}

$LocalAppData = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME 'AppData\Local' }
$InstallRoot = if ($env:SANMAO_CLAUDE_ROOT) { $env:SANMAO_CLAUDE_ROOT } else { Join-Path $LocalAppData 'smagent' }
$ConfigDir = if ($env:SANMAO_CLAUDE_CONFIG_DIR) { $env:SANMAO_CLAUDE_CONFIG_DIR } else { Join-Path $InstallRoot 'config' }
$StateDir = if ($env:SANMAO_CLAUDE_STATE_DIR) { $env:SANMAO_CLAUDE_STATE_DIR } else { Join-Path $InstallRoot 'state' }
$LegacyStateDir = Join-Path $HOME '.config\smagent'
$TunnelStart = if ($env:SANMAO_START_TUNNEL_SCRIPT) { $env:SANMAO_START_TUNNEL_SCRIPT } else { Join-Path $ConfigDir 'start-local-tunnel.ps1' }
$BaseUrl = if ($env:SANMAO_CLAUDE_BASE_URL) { $env:SANMAO_CLAUDE_BASE_URL } else { 'https://www.sanmao.fun' }
$ModelsUrl = if ($env:SANMAO_CLAUDE_MODELS_URL) { $env:SANMAO_CLAUDE_MODELS_URL } else { "$BaseUrl/v1/models" }
$DefaultModelFile = Join-Path $StateDir 'default-model'
$ConfigFile = Join-Path $StateDir 'config.env'
$LegacyDefaultModelFile = Join-Path $LegacyStateDir 'default-model'
$LegacyConfigFile = Join-Path $LegacyStateDir 'config.env'
$LegacyPs1ConfigFile = Join-Path $LegacyStateDir 'config.ps1env'
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

function Read-KeyValueToken($Path) {
    if (-not (Test-Path $Path)) { return $null }
    foreach ($line in Get-Content $Path) {
        if ($line -match '^\s*SANMAO_API_KEY=(.*)$') {
            return $Matches[1].Trim()
        }
    }
    return $null
}

function Read-LegacyToken($Path) {
    if (-not (Test-Path $Path)) { return $null }
    foreach ($line in Get-Content $Path) {
        if ($line -match '^\$env:SANMAO_API_KEY="(.+)"$') {
            return $Matches[1]
        }
    }
    return $null
}

function Load-ConfigToken {
    $token = Read-KeyValueToken $ConfigFile
    if ($token) { return $token }
    $token = Read-KeyValueToken $LegacyConfigFile
    if ($token) { return $token }
    return Read-LegacyToken $LegacyPs1ConfigFile
}

function Save-ConfigToken($Token) {
    Set-Content -Path $ConfigFile -Value "SANMAO_API_KEY=$Token" -Encoding UTF8
}

function Load-DefaultModel {
    if (Test-Path $DefaultModelFile) {
        return Get-Content $DefaultModelFile -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if (Test-Path $LegacyDefaultModelFile) {
        return Get-Content $LegacyDefaultModelFile -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    return $null
}

function Ensure-Tunnel {
    if ($SkipTunnel) { return }
    if (-not (Test-Path $TunnelStart)) {
        throw "[smagent] missing tunnel helper at $TunnelStart"
    }
    powershell.exe -ExecutionPolicy Bypass -File $TunnelStart | Out-Null
}

$token = $env:SANMAO_API_KEY
if (-not $token) { $token = $env:ANTHROPIC_API_KEY_SM }
if (-not $token) { $token = $env:ANTHROPIC_AUTH_TOKEN_SM }
if (-not $token) { $token = $env:ANTHROPIC_API_KEY }
if (-not $token) { $token = Load-ConfigToken }

if ($Setup) {
    if (-not $token) {
        $token = Read-Host 'Enter sanmao API key'
    }
    if (-not $token) {
        throw '[smagent] no API key provided'
    }
    Save-ConfigToken $token
    Write-Host "[smagent] saved token to $ConfigFile"
    exit 0
}

if (-not $token) {
    throw "[smagent] missing SANMAO_API_KEY, ANTHROPIC_API_KEY_SM, or stored config at $ConfigFile"
}

$env:ANTHROPIC_API_KEY = $token
$env:ANTHROPIC_BASE_URL = $BaseUrl
Remove-Item Env:ANTHROPIC_AUTH_TOKEN -ErrorAction SilentlyContinue

function Get-ModelFamily([string]$ModelName) {
    $lower = ($ModelName ?? '').Trim().ToLower()
    if ($lower.StartsWith('gpt-') -or $lower.StartsWith('codex-')) {
        return 'codex'
    }
    return 'ccr'
}

function Ensure-CCR {
    $ccrCmd = Get-Command ccr -ErrorAction SilentlyContinue
    if (-not $ccrCmd) {
        throw "[smagent] ccr is not installed or not on PATH.`n[smagent] install Claude Code Router first, then configure it for your sanmao-backed Claude-compatible models."
    }
}

function Ensure-CodexProxy {
    $proxyScript = if ($env:SMAGENT_CODEX_PROXY_SCRIPT) { $env:SMAGENT_CODEX_PROXY_SCRIPT } else { Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'start-codex-fallback-proxy.sh' }
    if (-not (Test-Path $proxyScript)) {
        throw "[smagent] codex backend requires $proxyScript"
    }
    & $proxyScript | Out-Null
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

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
    try {
        $payload = Invoke-RestMethod -Method Get -Headers $headers -Uri $ModelsUrl
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__ 2>$null
        if ($statusCode -eq 401) {
            throw "[smagent] token unauthorized. It may be disabled/expired, or the saved SANMAO_API_KEY is stale.`n[smagent] run smagent-setup with a fresh token, then retry."
        }
        throw "[smagent] failed to fetch models: $($_.Exception.Message)"
    }
    $ids = @($payload.data | ForEach-Object { $_.id })
    $ordered = @($priority | Where-Object { $ids -contains $_ })
    $remaining = @($ids | Where-Object { $ordered -notcontains $_ } | Sort-Object)
    return @($ordered + $remaining)
}

function Pick-FromModels($CurrentModel) {
    $models = Fetch-Models
    if (-not $models -or $models.Count -eq 0) {
        throw '[smagent] no models available from sanmao'
    }
    Write-Host 'Available sanmao-backed gateway models:'
    for ($index = 0; $index -lt $models.Count; $index++) {
        $marker = if ($CurrentModel -and $models[$index] -eq $CurrentModel) { ' *' } else { '  ' }
        '{0,2}.{1} {2}' -f ($index + 1), $marker, $models[$index] | Write-Host
    }
    Write-Host ''
    $choice = Read-Host 'Model'
    if (-not $choice) {
        throw '[smagent] model selection cancelled'
    }
    if ($choice -match '^[0-9]+$') {
        $selectedIndex = [int]$choice - 1
        if ($selectedIndex -ge 0 -and $selectedIndex -lt $models.Count) {
            return $models[$selectedIndex]
        }
        throw '[smagent] invalid selection'
    }
    if ($models -contains $choice) {
        return $choice
    }
    $matches = @($models | Where-Object { $_.ToLower().Contains($choice.ToLower()) })
    if ($matches.Count -eq 1) {
        return $matches[0]
    }
    if ($matches.Count -gt 1) {
        throw ('[smagent] ambiguous match: ' + ($matches -join ', '))
    }
    throw '[smagent] model not found'
}

if ($ClearDefault) {
    if (Test-Path $DefaultModelFile) { Remove-Item $DefaultModelFile -Force }
    if (Test-Path $LegacyDefaultModelFile) { Remove-Item $LegacyDefaultModelFile -Force }
}

if ($PrintEnv) {
    Ensure-Tunnel
    Write-Host "ANTHROPIC_BASE_URL=$BaseUrl"
    Write-Host 'ANTHROPIC_API_KEY is set'
    Write-Host 'ANTHROPIC_AUTH_TOKEN is unset'
    $currentDefaultForPrint = Load-DefaultModel
    if ($currentDefaultForPrint) {
        Write-Host "DEFAULT_MODEL=$currentDefaultForPrint"
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

$currentDefault = Load-DefaultModel
if (-not $Model -and -not $PickModel -and $ClaudeArgs.Count -eq 0 -and -not $currentDefault) {
    $PickModel = $true
}

$selectedModel = $Model
if ($PickModel) {
    $selectedModel = Pick-FromModels $currentDefault
}
elseif (-not $selectedModel -and $currentDefault) {
    $selectedModel = $currentDefault
}

if ($selectedModel -and $RememberModel -and -not $SessionOnly) {
    Set-Content -Path $DefaultModelFile -Value $selectedModel -Encoding UTF8
}

if ($selectedModel) {
    $family = Get-ModelFamily $selectedModel
    Write-Host "[smagent] launching model: $selectedModel" -ForegroundColor Yellow
    Write-Host "[smagent] selected backend family: $family" -ForegroundColor Yellow
    if ($RememberModel -and -not $SessionOnly) {
        Write-Host '[smagent] remembering model for future launches' -ForegroundColor Yellow
        Set-Content -Path $DefaultModelFile -Value $selectedModel -Encoding UTF8
    }
    else {
        Write-Host '[smagent] session-only model selection (not persisted)' -ForegroundColor Yellow
    }
    if ($family -eq 'codex') {
        Ensure-CodexProxy
        $codexCmd = Get-Command codex -ErrorAction Stop
        if ($ClaudeArgs.Count -gt 0) {
            & $codexCmd.Source --model $selectedModel @ClaudeArgs
        }
        else {
            & $codexCmd.Source --model $selectedModel
        }
        exit $LASTEXITCODE
    }
    Ensure-CCR
    $ccrCmd = Get-Command ccr -ErrorAction Stop
    if ($ClaudeArgs.Count -gt 0) {
        & $ccrCmd.Source code -- --model $selectedModel @ClaudeArgs
    }
    else {
        & $ccrCmd.Source code -- --model $selectedModel
    }
    exit $LASTEXITCODE
}

Ensure-CCR
$ccrCmd = Get-Command ccr -ErrorAction Stop
if ($ClaudeArgs.Count -gt 0) {
    & $ccrCmd.Source code @ClaudeArgs
}
else {
    & $ccrCmd.Source code
}
exit $LASTEXITCODE
