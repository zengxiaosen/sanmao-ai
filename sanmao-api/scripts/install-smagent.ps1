Param(
    [string]$InstallBinDir = "$HOME\AppData\Local\smagent\bin",
    [string]$InstallConfigDir = "$HOME\AppData\Local\smagent\config",
    [string]$InstallStateDir = "$HOME\AppData\Local\smagent\state",
    [switch]$SkipPathHint
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Ensure-Dir([string]$Path) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Set-TextFile([string]$Path, [string]$Content, [System.Text.Encoding]$Encoding) {
    [System.IO.File]::WriteAllText($Path, $Content, $Encoding)
}

function Copy-Runtime([string]$Name, [string]$DestinationDir) {
    Copy-Item -Path (Join-Path $ScriptDir $Name) -Destination (Join-Path $DestinationDir $Name) -Force
}

Ensure-Dir $InstallBinDir
Ensure-Dir $InstallConfigDir
Ensure-Dir $InstallStateDir

foreach ($runtime in @('smagent.ps1', 'smagent.mjs', 'smagent.py')) {
    Copy-Runtime $runtime $InstallBinDir
}
foreach ($runtime in @(
    'start-local-tunnel.ps1', 'start-local-tunnel.mjs', 'start-local-tunnel.py',
    'stop-local-tunnel.ps1', 'stop-local-tunnel.mjs', 'stop-local-tunnel.py'
)) {
    Copy-Runtime $runtime $InstallConfigDir
}

$psEncoding = New-Object System.Text.UTF8Encoding($false)
$asciiEncoding = [System.Text.Encoding]::ASCII

function New-PsWrapper([string]$Path, [string[]]$FixedArgs, [bool]$UsePickWhenEmpty) {
    $fixedArgsLiteral = if ($FixedArgs.Count -gt 0) {
        '@(' + (($FixedArgs | ForEach-Object { "'{0}'" -f ($_ -replace "'", "''") }) -join ', ') + ')'
    }
    else {
        '@()'
    }

    $content = @"
Param([Parameter(ValueFromRemainingArguments = `$true)][string[]]`$ArgsFromCmd)
`$ErrorActionPreference = 'Stop'
`$env:SANMAO_CLAUDE_CONFIG_DIR = '$($InstallConfigDir -replace "'", "''")'
`$env:SANMAO_CLAUDE_STATE_DIR = '$($InstallStateDir -replace "'", "''")'
`$env:SANMAO_START_TUNNEL_SCRIPT = '$(Join-Path $InstallConfigDir 'start-local-tunnel.ps1' -replace "'", "''")'
`$fixedArgs = $fixedArgsLiteral
if ($UsePickWhenEmpty -and `$ArgsFromCmd.Count -eq 0 -and `$fixedArgs.Count -eq 0) {
  & (Join-Path `$PSScriptRoot 'smagent.ps1') pick
} else {
  & (Join-Path `$PSScriptRoot 'smagent.ps1') @fixedArgs @ArgsFromCmd
}
exit `$LASTEXITCODE
"@
    Set-TextFile -Path $Path -Content $content -Encoding $psEncoding
}

function New-MjsWrapper([string]$Path, [string[]]$FixedArgs, [bool]$UsePickWhenEmpty) {
    $fixedArgsJson = if ($FixedArgs.Count -gt 0) { ($FixedArgs | ConvertTo-Json -Compress) } else { '[]' }
    $usePickLiteral = if ($UsePickWhenEmpty) { 'true' } else { 'false' }
    $configDirJson = ConvertTo-Json -Compress $InstallConfigDir
    $stateDirJson = ConvertTo-Json -Compress $InstallStateDir
    $tunnelScriptJson = ConvertTo-Json -Compress (Join-Path $InstallConfigDir 'start-local-tunnel.mjs')
    $content = @"
#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const fixedArgs = $fixedArgsJson;
const argsFromCmd = process.argv.slice(2);
const finalArgs = ($usePickLiteral && argsFromCmd.length === 0 && fixedArgs.length === 0)
  ? ['pick']
  : [...fixedArgs, ...argsFromCmd];
const env = {
  ...process.env,
  SANMAO_CLAUDE_CONFIG_DIR: $configDirJson,
  SANMAO_CLAUDE_STATE_DIR: $stateDirJson,
  SANMAO_START_TUNNEL_SCRIPT: $tunnelScriptJson,
};
const result = spawnSync(process.execPath, [path.join(scriptDir, 'smagent.mjs'), ...finalArgs], {
  stdio: 'inherit',
  env,
  windowsHide: true,
});
if (result.error) {
  throw result.error;
}
process.exit(result.status ?? 1);
"@
    Set-TextFile -Path $Path -Content $content -Encoding $psEncoding
}

function New-PyWrapper([string]$Path, [string[]]$FixedArgs, [bool]$UsePickWhenEmpty) {
    $fixedArgsPy = if ($FixedArgs.Count -gt 0) {
        '[' + (($FixedArgs | ForEach-Object { "'{0}'" -f ($_ -replace "'", "\\'") }) -join ', ') + ']'
    }
    else {
        '[]'
    }
    $usePickLiteral = if ($UsePickWhenEmpty) { 'True' } else { 'False' }
    $content = @"
#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FIXED_ARGS = $fixedArgsPy
args_from_cmd = sys.argv[1:]
if $usePickLiteral and len(args_from_cmd) == 0 and len(FIXED_ARGS) == 0:
    final_args = ['pick']
else:
    final_args = [*FIXED_ARGS, *args_from_cmd]
env = dict(os.environ)
env['SANMAO_CLAUDE_CONFIG_DIR'] = r'$($InstallConfigDir -replace "'", "''")'
env['SANMAO_CLAUDE_STATE_DIR'] = r'$($InstallStateDir -replace "'", "''")'
env['SANMAO_START_TUNNEL_SCRIPT'] = r'$(Join-Path $InstallConfigDir 'start-local-tunnel.py' -replace "'", "''")'
raise SystemExit(subprocess.run([sys.executable, str(SCRIPT_DIR / 'smagent.py'), *final_args], env=env, check=False).returncode)
"@
    Set-TextFile -Path $Path -Content $content -Encoding $psEncoding
}

function New-CmdWrapper([string]$Path, [string]$BaseName) {
    $content = @"
@echo off
set "SANMAO_CLAUDE_CONFIG_DIR=$InstallConfigDir"
set "SANMAO_CLAUDE_STATE_DIR=$InstallStateDir"
where node >nul 2>nul
if %ERRORLEVEL%==0 (
  node "%~dp0$BaseName.mjs" %*
  exit /b %ERRORLEVEL%
)
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python "%~dp0$BaseName.py" %*
  exit /b %ERRORLEVEL%
)
powershell.exe -ExecutionPolicy Bypass -File "%~dp0$BaseName.ps1" %*
"@
    Set-TextFile -Path $Path -Content $content -Encoding $asciiEncoding
}

New-PsWrapper (Join-Path $InstallBinDir 'smagent.ps1') @() $true
New-PsWrapper (Join-Path $InstallBinDir 'smagent-models.ps1') @('models') $false
New-PsWrapper (Join-Path $InstallBinDir 'smagent-pick.ps1') @('pick') $false
New-PsWrapper (Join-Path $InstallBinDir 'smagent-setup.ps1') @('setup') $false
New-PsWrapper (Join-Path $InstallBinDir 'smagent.ps1') @() $true
New-PsWrapper (Join-Path $InstallBinDir 'smagent-models.ps1') @('models') $false
New-PsWrapper (Join-Path $InstallBinDir 'smagent-pick.ps1') @('pick') $false
New-PsWrapper (Join-Path $InstallBinDir 'smagent-setup.ps1') @('setup') $false

New-MjsWrapper (Join-Path $InstallBinDir 'smagent.mjs') @() $true
New-MjsWrapper (Join-Path $InstallBinDir 'smagent-models.mjs') @('models') $false
New-MjsWrapper (Join-Path $InstallBinDir 'smagent-pick.mjs') @('pick') $false
New-MjsWrapper (Join-Path $InstallBinDir 'smagent-setup.mjs') @('setup') $false
New-MjsWrapper (Join-Path $InstallBinDir 'smagent.mjs') @() $true
New-MjsWrapper (Join-Path $InstallBinDir 'smagent-models.mjs') @('models') $false
New-MjsWrapper (Join-Path $InstallBinDir 'smagent-pick.mjs') @('pick') $false
New-MjsWrapper (Join-Path $InstallBinDir 'smagent-setup.mjs') @('setup') $false

New-PyWrapper (Join-Path $InstallBinDir 'smagent.py') @() $true
New-PyWrapper (Join-Path $InstallBinDir 'smagent-models.py') @('models') $false
New-PyWrapper (Join-Path $InstallBinDir 'smagent-pick.py') @('pick') $false
New-PyWrapper (Join-Path $InstallBinDir 'smagent-setup.py') @('setup') $false
New-PyWrapper (Join-Path $InstallBinDir 'smagent.py') @() $true
New-PyWrapper (Join-Path $InstallBinDir 'smagent-models.py') @('models') $false
New-PyWrapper (Join-Path $InstallBinDir 'smagent-pick.py') @('pick') $false
New-PyWrapper (Join-Path $InstallBinDir 'smagent-setup.py') @('setup') $false

New-CmdWrapper (Join-Path $InstallBinDir 'smagent.cmd') 'smagent'
New-CmdWrapper (Join-Path $InstallBinDir 'smagent-models.cmd') 'smagent-models'
New-CmdWrapper (Join-Path $InstallBinDir 'smagent-pick.cmd') 'smagent-pick'
New-CmdWrapper (Join-Path $InstallBinDir 'smagent-setup.cmd') 'smagent-setup'
New-CmdWrapper (Join-Path $InstallBinDir 'smagent.cmd') 'smagent'
New-CmdWrapper (Join-Path $InstallBinDir 'smagent-models.cmd') 'smagent-models'
New-CmdWrapper (Join-Path $InstallBinDir 'smagent-pick.cmd') 'smagent-pick'
New-CmdWrapper (Join-Path $InstallBinDir 'smagent-setup.cmd') 'smagent-setup'

Write-Host "[smagent-install] installed launchers into $InstallBinDir"
Write-Host "[smagent-install] config dir: $InstallConfigDir"
Write-Host "[smagent-install] state dir: $InstallStateDir"
if (-not $SkipPathHint) {
    Write-Host ''
    Write-Host 'If these commands are not found in a new terminal, add this user bin directory to PATH:'
    Write-Host "  $InstallBinDir"
    Write-Host 'Then open a new PowerShell window.'
}
Write-Host '[smagent-install] supported entrypoints:'
Write-Host "  - powershell.exe -ExecutionPolicy Bypass -File $InstallBinDir\smagent.ps1"
Write-Host "  - node $InstallBinDir\smagent.mjs"
Write-Host "  - python $InstallBinDir\smagent.py"
Write-Host '[smagent-install] next steps:'
Write-Host "  1. $InstallBinDir\smagent-setup.cmd"
Write-Host "  2. $InstallBinDir\smagent-models.cmd"
Write-Host "  3. $InstallBinDir\smagent.cmd or $InstallBinDir\smagent-pick.cmd (smagent aliases also installed)"
