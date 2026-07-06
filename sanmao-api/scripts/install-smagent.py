#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


def get_local_appdata() -> Path:
    local_appdata = os.environ.get('LOCALAPPDATA')
    if local_appdata:
        return Path(local_appdata)
    return Path.home() / 'AppData' / 'Local'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    default_root = get_local_appdata() / 'smagent'
    parser.add_argument('--install-bin-dir', default=str(default_root / 'bin'))
    parser.add_argument('--install-config-dir', default=str(default_root / 'config'))
    parser.add_argument('--install-state-dir', default=str(default_root / 'state'))
    parser.add_argument('--skip-path-hint', action='store_true')
    return parser


def write_text(path: Path, content: str, encoding: str = 'utf-8') -> None:
    path.write_text(content, encoding=encoding)


def ps_quote(value: str) -> str:
    return value.replace("'", "''")


def ps_wrapper(config_dir: Path, state_dir: Path, fixed_args: list[str], use_pick_when_empty: bool) -> str:
    if fixed_args:
        fixed_args_literal = '@(' + ', '.join("'{}'".format(ps_quote(arg)) for arg in fixed_args) + ')'
    else:
        fixed_args_literal = '@()'
    use_pick_literal = '$true' if use_pick_when_empty else '$false'
    tunnel_script = config_dir / 'start-local-tunnel.ps1'
    return (
        "Param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ArgsFromCmd)\n"
        "$ErrorActionPreference = 'Stop'\n"
        f"$env:SANMAO_CLAUDE_CONFIG_DIR = '{ps_quote(str(config_dir))}'\n"
        f"$env:SANMAO_CLAUDE_STATE_DIR = '{ps_quote(str(state_dir))}'\n"
        f"$env:SANMAO_START_TUNNEL_SCRIPT = '{ps_quote(str(tunnel_script))}'\n"
        f"$fixedArgs = {fixed_args_literal}\n"
        f"if ({use_pick_literal} -and $ArgsFromCmd.Count -eq 0 -and $fixedArgs.Count -eq 0) {{\n"
        "  & (Join-Path $PSScriptRoot 'smagent.ps1') pick\n"
        "} else {\n"
        "  & (Join-Path $PSScriptRoot 'smagent.ps1') @fixedArgs @ArgsFromCmd\n"
        "}\n"
        "exit $LASTEXITCODE\n"
    )


def mjs_wrapper(config_dir: Path, state_dir: Path, fixed_args: list[str], use_pick_when_empty: bool) -> str:
    tunnel_script = config_dir / 'start-local-tunnel.mjs'
    return f"""#!/usr/bin/env node
import {{ spawnSync }} from 'node:child_process';
import path from 'node:path';
import {{ fileURLToPath }} from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const fixedArgs = {json.dumps(fixed_args)};
const argsFromCmd = process.argv.slice(2);
const finalArgs = ({str(use_pick_when_empty).lower()} && argsFromCmd.length === 0 && fixedArgs.length === 0)
  ? ['pick']
  : [...fixedArgs, ...argsFromCmd];
const env = {{
  ...process.env,
  SANMAO_CLAUDE_CONFIG_DIR: {json.dumps(str(config_dir))},
  SANMAO_CLAUDE_STATE_DIR: {json.dumps(str(state_dir))},
  SANMAO_START_TUNNEL_SCRIPT: {json.dumps(str(tunnel_script))},
}};
const result = spawnSync(process.execPath, [path.join(scriptDir, 'smagent.mjs'), ...finalArgs], {{ stdio: 'inherit', env, windowsHide: true }});
if (result.error) {{
  throw result.error;
}}
process.exit(result.status ?? 1);
"""


def py_wrapper(config_dir: Path, state_dir: Path, fixed_args: list[str], use_pick_when_empty: bool) -> str:
    tunnel_script = config_dir / 'start-local-tunnel.py'
    return f"""#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FIXED_ARGS = {fixed_args!r}
args_from_cmd = sys.argv[1:]
if {use_pick_when_empty!r} and len(args_from_cmd) == 0 and len(FIXED_ARGS) == 0:
    final_args = ['pick']
else:
    final_args = [*FIXED_ARGS, *args_from_cmd]
env = dict(os.environ)
env['SANMAO_CLAUDE_CONFIG_DIR'] = {str(config_dir)!r}
env['SANMAO_CLAUDE_STATE_DIR'] = {str(state_dir)!r}
env['SANMAO_START_TUNNEL_SCRIPT'] = {str(tunnel_script)!r}
raise SystemExit(subprocess.run([sys.executable, str(SCRIPT_DIR / 'smagent.py'), *final_args], env=env, check=False).returncode)
"""


def cmd_wrapper(config_dir: Path, state_dir: Path, base_name: str) -> str:
    return f"""@echo off
set "SANMAO_CLAUDE_CONFIG_DIR={config_dir}"
set "SANMAO_CLAUDE_STATE_DIR={state_dir}"
where node >nul 2>nul
if %ERRORLEVEL%==0 (
  node "%~dp0{base_name}.mjs" %*
  exit /b %ERRORLEVEL%
)
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python "%~dp0{base_name}.py" %*
  exit /b %ERRORLEVEL%
)
powershell.exe -ExecutionPolicy Bypass -File "%~dp0{base_name}.ps1" %*
"""


def main() -> int:
    args = build_parser().parse_args()
    install_bin_dir = Path(args.install_bin_dir)
    install_config_dir = Path(args.install_config_dir)
    install_state_dir = Path(args.install_state_dir)
    script_dir = Path(__file__).resolve().parent

    install_bin_dir.mkdir(parents=True, exist_ok=True)
    install_config_dir.mkdir(parents=True, exist_ok=True)
    install_state_dir.mkdir(parents=True, exist_ok=True)

    for runtime in ['smagent.ps1', 'smagent.mjs', 'smagent.py']:
        shutil.copyfile(script_dir / runtime, install_bin_dir / runtime)
    for runtime in [
        'start-local-tunnel.ps1', 'start-local-tunnel.mjs', 'start-local-tunnel.py',
        'stop-local-tunnel.ps1', 'stop-local-tunnel.mjs', 'stop-local-tunnel.py',
    ]:
        shutil.copyfile(script_dir / runtime, install_config_dir / runtime)

    wrappers = [
        ('smagent', [], True),
        ('smagent-models', ['models'], False),
        ('smagent-pick', ['pick'], False),
        ('smagent-setup', ['setup'], False),
    ]

    for base_name, fixed_args, use_pick_when_empty in wrappers:
        write_text(install_bin_dir / f'{base_name}.ps1', ps_wrapper(install_config_dir, install_state_dir, fixed_args, use_pick_when_empty))
        write_text(install_bin_dir / f'{base_name}.mjs', mjs_wrapper(install_config_dir, install_state_dir, fixed_args, use_pick_when_empty))
        write_text(install_bin_dir / f'{base_name}.py', py_wrapper(install_config_dir, install_state_dir, fixed_args, use_pick_when_empty))
        write_text(install_bin_dir / f'{base_name}.cmd', cmd_wrapper(install_config_dir, install_state_dir, base_name), encoding='ascii')

    print(f'[smagent-install] installed launchers into {install_bin_dir}')
    print(f'[smagent-install] config dir: {install_config_dir}')
    print(f'[smagent-install] state dir: {install_state_dir}')
    if not args.skip_path_hint:
        print('')
        print('If these commands are not found in a new terminal, add this user bin directory to PATH:')
        print(f'  {install_bin_dir}')
        print('Then open a new terminal window.')
    print('[smagent-install] supported entrypoints:')
    print(f'  - powershell.exe -ExecutionPolicy Bypass -File {install_bin_dir / "smagent.ps1"}')
    print(f'  - node {install_bin_dir / "smagent.mjs"}')
    print(f'  - python {install_bin_dir / "smagent.py"}')
    print('[smagent-install] next steps:')
    print(f'  1. {install_bin_dir / "smagent-setup.cmd"}')
    print(f'  2. {install_bin_dir / "smagent-models.cmd"}')
    print(f'  3. {install_bin_dir / "smagent.cmd"} or {install_bin_dir / "smagent-pick.cmd"} (smagent aliases also installed)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
