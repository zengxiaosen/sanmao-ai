#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const scriptDir = path.dirname(__filename);
const localAppData = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');

function parseArgs(argv) {
  const options = {
    installBinDir: path.join(localAppData, 'smagent', 'bin'),
    installConfigDir: path.join(localAppData, 'smagent', 'config'),
    installStateDir: path.join(localAppData, 'smagent', 'state'),
    skipPathHint: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--skip-path-hint') {
      options.skipPathHint = true;
      continue;
    }
    if (arg === '--install-bin-dir' && index + 1 < argv.length) {
      options.installBinDir = argv[index + 1];
      index += 1;
      continue;
    }
    if (arg === '--install-config-dir' && index + 1 < argv.length) {
      options.installConfigDir = argv[index + 1];
      index += 1;
      continue;
    }
    if (arg === '--install-state-dir' && index + 1 < argv.length) {
      options.installStateDir = argv[index + 1];
      index += 1;
      continue;
    }
    throw new Error(`unknown argument: ${arg}`);
  }

  return options;
}

async function ensureDir(targetPath) {
  await fs.mkdir(targetPath, { recursive: true });
}

async function copyRuntime(name, destinationDir) {
  await fs.copyFile(path.join(scriptDir, name), path.join(destinationDir, name));
}

function psWrapper(configDir, stateDir, fixedArgs, usePickWhenEmpty) {
  const fixedArgsLiteral = fixedArgs.length ? `@(${fixedArgs.map((arg) => `'${arg.replace(/'/g, "''")}'`).join(', ')})` : '@()';
  return `Param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ArgsFromCmd)\n$ErrorActionPreference = 'Stop'\n$env:SANMAO_CLAUDE_CONFIG_DIR = '${configDir.replace(/'/g, "''")}'\n$env:SANMAO_CLAUDE_STATE_DIR = '${stateDir.replace(/'/g, "''")}'\n$env:SANMAO_START_TUNNEL_SCRIPT = '${path.join(configDir, 'start-local-tunnel.ps1').replace(/'/g, "''")}'\n$fixedArgs = ${fixedArgsLiteral}\nif (${usePickWhenEmpty ? '$true' : '$false'} -and $ArgsFromCmd.Count -eq 0 -and $fixedArgs.Count -eq 0) {\n  & (Join-Path $PSScriptRoot 'smagent.ps1') pick\n} else {\n  & (Join-Path $PSScriptRoot 'smagent.ps1') @fixedArgs @ArgsFromCmd\n}\nexit $LASTEXITCODE\n`;
}

function mjsWrapper(configDir, stateDir, fixedArgs, usePickWhenEmpty) {
  return `#!/usr/bin/env node\nimport { spawnSync } from 'node:child_process';\nimport path from 'node:path';\nimport { fileURLToPath } from 'node:url';\n\nconst scriptDir = path.dirname(fileURLToPath(import.meta.url));\nconst fixedArgs = ${JSON.stringify(fixedArgs)};\nconst argsFromCmd = process.argv.slice(2);\nconst finalArgs = (${usePickWhenEmpty ? 'true' : 'false'} && argsFromCmd.length === 0 && fixedArgs.length === 0)\n  ? ['pick']\n  : [...fixedArgs, ...argsFromCmd];\nconst env = {\n  ...process.env,\n  SANMAO_CLAUDE_CONFIG_DIR: ${JSON.stringify(configDir)},\n  SANMAO_CLAUDE_STATE_DIR: ${JSON.stringify(stateDir)},\n  SANMAO_START_TUNNEL_SCRIPT: ${JSON.stringify(path.join(configDir, 'start-local-tunnel.mjs'))},\n};\nconst result = spawnSync(process.execPath, [path.join(scriptDir, 'smagent.mjs'), ...finalArgs], { stdio: 'inherit', env, windowsHide: true });\nif (result.error) { throw result.error; }\nprocess.exit(result.status ?? 1);\n`;
}

function pyWrapper(configDir, stateDir, fixedArgs, usePickWhenEmpty) {
  return `#!/usr/bin/env python3\nimport os\nimport subprocess\nimport sys\nfrom pathlib import Path\n\nSCRIPT_DIR = Path(__file__).resolve().parent\nFIXED_ARGS = ${JSON.stringify(fixedArgs)}\nargs_from_cmd = sys.argv[1:]\nif ${usePickWhenEmpty ? 'True' : 'False'} and len(args_from_cmd) == 0 and len(FIXED_ARGS) == 0:\n    final_args = ['pick']\nelse:\n    final_args = [*FIXED_ARGS, *args_from_cmd]\nenv = dict(os.environ)\nenv['SANMAO_CLAUDE_CONFIG_DIR'] = r${JSON.stringify(configDir)}\nenv['SANMAO_CLAUDE_STATE_DIR'] = r${JSON.stringify(stateDir)}\nenv['SANMAO_START_TUNNEL_SCRIPT'] = r${JSON.stringify(path.join(configDir, 'start-local-tunnel.py'))}\nraise SystemExit(subprocess.run([sys.executable, str(SCRIPT_DIR / 'smagent.py'), *final_args], env=env, check=False).returncode)\n`;
}

function cmdWrapper(configDir, stateDir, baseName) {
  return `@echo off\nset "SANMAO_CLAUDE_CONFIG_DIR=${configDir}"\nset "SANMAO_CLAUDE_STATE_DIR=${stateDir}"\nwhere node >nul 2>nul\nif %ERRORLEVEL%==0 (\n  node "%~dp0${baseName}.mjs" %*\n  exit /b %ERRORLEVEL%\n)\nwhere python >nul 2>nul\nif %ERRORLEVEL%==0 (\n  python "%~dp0${baseName}.py" %*\n  exit /b %ERRORLEVEL%\n)\npowershell.exe -ExecutionPolicy Bypass -File "%~dp0${baseName}.ps1" %*\n`;
}

async function writeText(targetPath, content) {
  await fs.writeFile(targetPath, content, 'utf8');
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  await ensureDir(options.installBinDir);
  await ensureDir(options.installConfigDir);
  await ensureDir(options.installStateDir);

  for (const runtime of ['smagent.ps1', 'smagent.mjs', 'smagent.py']) {
    await copyRuntime(runtime, options.installBinDir);
  }
  for (const runtime of [
    'start-local-tunnel.ps1', 'start-local-tunnel.mjs', 'start-local-tunnel.py',
    'stop-local-tunnel.ps1', 'stop-local-tunnel.mjs', 'stop-local-tunnel.py',
  ]) {
    await copyRuntime(runtime, options.installConfigDir);
  }

  const wrappers = [
    { base: 'smagent', fixedArgs: [], usePickWhenEmpty: true },
    { base: 'smagent-models', fixedArgs: ['models'], usePickWhenEmpty: false },
    { base: 'smagent-pick', fixedArgs: ['pick'], usePickWhenEmpty: false },
    { base: 'smagent-setup', fixedArgs: ['setup'], usePickWhenEmpty: false },
  ];

  for (const wrapper of wrappers) {
    await writeText(path.join(options.installBinDir, `${wrapper.base}.ps1`), psWrapper(options.installConfigDir, options.installStateDir, wrapper.fixedArgs, wrapper.usePickWhenEmpty));
    await writeText(path.join(options.installBinDir, `${wrapper.base}.mjs`), mjsWrapper(options.installConfigDir, options.installStateDir, wrapper.fixedArgs, wrapper.usePickWhenEmpty));
    await writeText(path.join(options.installBinDir, `${wrapper.base}.py`), pyWrapper(options.installConfigDir, options.installStateDir, wrapper.fixedArgs, wrapper.usePickWhenEmpty));
    await fs.writeFile(path.join(options.installBinDir, `${wrapper.base}.cmd`), cmdWrapper(options.installConfigDir, options.installStateDir, wrapper.base), 'ascii');
  }

  console.log(`[smagent-install] installed launchers into ${options.installBinDir}`);
  console.log(`[smagent-install] config dir: ${options.installConfigDir}`);
  console.log(`[smagent-install] state dir: ${options.installStateDir}`);
  if (!options.skipPathHint) {
    console.log('');
    console.log('If these commands are not found in a new terminal, add this user bin directory to PATH:');
    console.log(`  ${options.installBinDir}`);
    console.log('Then open a new terminal window.');
  }
  console.log('[smagent-install] supported entrypoints:');
  console.log(`  - powershell.exe -ExecutionPolicy Bypass -File ${path.join(options.installBinDir, 'smagent.ps1')}`);
  console.log(`  - node ${path.join(options.installBinDir, 'smagent.mjs')}`);
  console.log(`  - python ${path.join(options.installBinDir, 'smagent.py')}`);
  console.log('[smagent-install] next steps:');
  console.log(`  1. ${path.join(options.installBinDir, 'smagent-setup.cmd')}`);
  console.log(`  2. ${path.join(options.installBinDir, 'smagent-models.cmd')}`);
  console.log(`  3. ${path.join(options.installBinDir, 'smagent.cmd')} or ${path.join(options.installBinDir, 'smagent-pick.cmd')} (smagent aliases also installed)`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
