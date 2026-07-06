#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODEL_PRIORITY = [
    'glm-5.2', 'glm-5.1', 'glm-5',
    'qwen3.7-max', 'qwen3.7-plus',
    'deepseek-v4-pro', 'deepseek-v4-flash',
    'claude-opus-4-8', 'claude-opus-4-7', 'claude-opus-4-6',
    'claude-sonnet-4-6', 'claude-sonnet-4-5-20250929', 'claude-haiku-4-5-20251001',
    'gpt-5.5', 'gpt-5.4', 'gpt-5.4-mini', 'gpt-5.3-codex-spark', 'codex-auto-review',
]


def get_local_appdata() -> Path:
    local_appdata = os.environ.get('LOCALAPPDATA')
    if local_appdata:
        return Path(local_appdata)
    return Path.home() / 'AppData' / 'Local'


def parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('command', nargs='?')
    parser.add_argument('--print-env', action='store_true')
    parser.add_argument('--skip-tunnel', action='store_true')
    parser.add_argument('--list-models', action='store_true')
    parser.add_argument('--pick-model', action='store_true')
    parser.add_argument('--session-only', action='store_true')
    parser.add_argument('--clear-default-model', action='store_true')
    parser.add_argument('--remember-model', action='store_true')
    parser.add_argument('--setup', action='store_true')
    parser.add_argument('--model')
    args, rest = parser.parse_known_args(argv)

    if args.command == 'models':
        args.list_models = True
    elif args.command == 'pick':
        args.pick_model = True
    elif args.command == 'setup':
        args.setup = True
    elif args.command == 'clear-default':
        args.clear_default_model = True
    elif args.command:
        rest = [args.command, *rest]
        args.command = None

    return args, rest


def read_env_token(file_path: Path) -> str:
    if not file_path.exists():
        return ''
    for line in file_path.read_text(encoding='utf-8').splitlines():
        if line.startswith('SANMAO_API_KEY='):
            return line.split('=', 1)[1].strip()
    return ''


def read_legacy_ps1_token(file_path: Path) -> str:
    if not file_path.exists():
        return ''
    prefix = '$env:SANMAO_API_KEY="'
    suffix = '"'
    for line in file_path.read_text(encoding='utf-8').splitlines():
        if line.startswith(prefix) and line.endswith(suffix):
            return line[len(prefix):-len(suffix)]
    return ''


def read_first_line(file_path: Path) -> str:
    if not file_path.exists():
        return ''
    return file_path.read_text(encoding='utf-8').splitlines()[0].strip()


def save_token(config_file: Path, token: str) -> None:
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(f'SANMAO_API_KEY={token}\n', encoding='utf-8')


def script_command(target: Path) -> list[str]:
    lowered = target.name.lower()
    if lowered.endswith('.py'):
        return [sys.executable, str(target)]
    if lowered.endswith('.mjs'):
        return ['node', str(target)]
    if lowered.endswith('.ps1'):
        return ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-File', str(target)]
    return [str(target)]


def ensure_tunnel(skip_tunnel: bool, tunnel_script: Path) -> None:
    if skip_tunnel:
        return
    if not tunnel_script.exists():
        raise SystemExit(f'[smagent] missing tunnel helper at {tunnel_script}')
    result = subprocess.run(script_command(tunnel_script), check=False, capture_output=True, text=True)
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def fetch_models(models_url: str, token: str) -> list[str]:
    request = urllib.request.Request(
        models_url,
        headers={
            'x-api-key': token,
            'anthropic-version': '2023-06-01',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise SystemExit('[smagent] token unauthorized. It may be disabled/expired, or the saved SANMAO_API_KEY is stale.\n[smagent] run smagent-setup with a fresh token, then retry.')
        raise SystemExit(f'[smagent] failed to fetch models: HTTP {exc.code}')
    except Exception as exc:
        raise SystemExit(f'[smagent] failed to fetch models: {exc}')
    ids = [item.get('id') for item in payload.get('data', []) if isinstance(item, dict) and item.get('id')]
    ordered = [model for model in MODEL_PRIORITY if model in ids]
    remaining = sorted(model for model in ids if model not in ordered)
    return ordered + remaining


def pick_model(current_model: str, models: list[str]) -> str:
    if not models:
        raise SystemExit('[smagent] no models available from sanmao')
    print('Available sanmao-backed gateway models:')
    for index, model in enumerate(models, start=1):
        marker = ' *' if current_model and model == current_model else '  '
        print(f'{index:2d}.{marker} {model}')
    print('')
    choice = input('Model ').strip()
    if not choice:
        raise SystemExit('[smagent] model selection cancelled')
    if choice.isdigit():
        selected_index = int(choice) - 1
        if 0 <= selected_index < len(models):
            return models[selected_index]
        raise SystemExit('[smagent] invalid selection')
    if choice in models:
        return choice
    matches = [model for model in models if choice.lower() in model.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SystemExit(f"[smagent] ambiguous match: {', '.join(matches)}")
    raise SystemExit('[smagent] model not found')


def classify_model_family(model: str) -> str:
    lowered = (model or '').strip().lower()
    if lowered.startswith('gpt-') or lowered.startswith('codex-'):
        return 'codex'
    return 'ccr'


def ensure_ccr() -> None:
    if shutil.which('ccr') is None:
        raise SystemExit('[smagent] ccr is not installed or not on PATH.\n[smagent] install Claude Code Router first, then configure it for your sanmao-backed Claude-compatible models.')


def ensure_codex_proxy(script_dir: Path) -> None:
    proxy_script = Path(os.environ.get('SMAGENT_CODEX_PROXY_SCRIPT', script_dir / 'start-codex-fallback-proxy.sh'))
    if not proxy_script.exists():
        raise SystemExit(f'[smagent] codex backend requires {proxy_script}')
    result = subprocess.run([str(proxy_script)], check=False, capture_output=True, text=True)
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def run_dispatched_backend(model: str, extra_args: list[str], env: dict[str, str], remember_model: bool, session_only: bool, script_dir: Path) -> int:
    family = classify_model_family(model)
    print(f'[smagent] launching model: {model}', file=sys.stderr)
    print(f'[smagent] selected backend family: {family}', file=sys.stderr)
    if remember_model and not session_only:
        print('[smagent] remembering model for future launches', file=sys.stderr)
    else:
        print('[smagent] session-only model selection (not persisted)', file=sys.stderr)

    if family == 'codex':
        ensure_codex_proxy(script_dir)
        command = ['codex', '--model', model, *extra_args]
        completed = subprocess.run(command, check=False)
        return completed.returncode

    ensure_ccr()
    command = ['ccr', 'code', '--', '--model', model, *extra_args]
    completed = subprocess.run(command, env=env, check=False)
    return completed.returncode


def main() -> int:
    args, claude_args = parse_args(sys.argv[1:])

    install_root = Path(os.environ.get('SANMAO_CLAUDE_ROOT', get_local_appdata() / 'smagent'))
    config_dir = Path(os.environ.get('SANMAO_CLAUDE_CONFIG_DIR', install_root / 'config'))
    state_dir = Path(os.environ.get('SANMAO_CLAUDE_STATE_DIR', install_root / 'state'))
    legacy_state_dir = Path.home() / '.config' / 'smagent'
    tunnel_script = Path(os.environ.get('SANMAO_START_TUNNEL_SCRIPT', config_dir / 'start-local-tunnel.py'))
    base_url = os.environ.get('SANMAO_CLAUDE_BASE_URL', 'https://www.sanmao.fun')
    models_url = os.environ.get('SANMAO_CLAUDE_MODELS_URL', f'{base_url}/v1/models')
    default_model_file = state_dir / 'default-model'
    config_file = state_dir / 'config.env'
    legacy_default_model_file = legacy_state_dir / 'default-model'
    legacy_config_file = legacy_state_dir / 'config.env'
    legacy_ps1_config_file = legacy_state_dir / 'config.ps1env'

    state_dir.mkdir(parents=True, exist_ok=True)

    token = (
        os.environ.get('SANMAO_API_KEY')
        or os.environ.get('ANTHROPIC_API_KEY_SM')
        or os.environ.get('ANTHROPIC_AUTH_TOKEN_SM')
        or os.environ.get('ANTHROPIC_API_KEY')
        or ''
    )
    if not token:
        token = read_env_token(config_file) or read_env_token(legacy_config_file) or read_legacy_ps1_token(legacy_ps1_config_file)

    if args.setup:
        if not token:
            token = input('Enter sanmao API key: ').strip()
        if not token:
            raise SystemExit('[smagent] no API key provided')
        save_token(config_file, token)
        print(f'[smagent] saved token to {config_file}')
        return 0

    if not token:
        raise SystemExit(f'[smagent] missing SANMAO_API_KEY, ANTHROPIC_API_KEY_SM, or stored config at {config_file}')

    if args.clear_default_model:
        default_model_file.unlink(missing_ok=True)
        legacy_default_model_file.unlink(missing_ok=True)

    ensure_tunnel(args.skip_tunnel, tunnel_script)

    current_default = read_first_line(default_model_file) or read_first_line(legacy_default_model_file)

    if args.print_env:
        print(f'ANTHROPIC_BASE_URL={base_url}')
        print('ANTHROPIC_API_KEY is set')
        print('ANTHROPIC_AUTH_TOKEN is unset')
        if current_default:
            print(f'DEFAULT_MODEL={current_default}')
        else:
            print('DEFAULT_MODEL is not set')
        print(f'CONFIG_FILE={config_file}')
        return 0

    runtime_env = dict(os.environ)
    runtime_env['ANTHROPIC_API_KEY'] = token
    runtime_env['ANTHROPIC_BASE_URL'] = base_url
    runtime_env.pop('ANTHROPIC_AUTH_TOKEN', None)

    if args.list_models:
        for model in fetch_models(models_url, token):
            print(model)
        return 0

    selected_model = args.model or ''
    should_pick = args.pick_model
    if not selected_model and not should_pick and not claude_args and not current_default:
        should_pick = True

    if should_pick:
        selected_model = pick_model(current_default, fetch_models(models_url, token))
    elif not selected_model and current_default:
        selected_model = current_default

    if selected_model and args.remember_model and not args.session_only:
        default_model_file.write_text(f'{selected_model}\n', encoding='utf-8')

    return run_dispatched_backend(selected_model, claude_args, runtime_env, args.remember_model, args.session_only, Path(__file__).resolve().parent)


if __name__ == '__main__':
    raise SystemExit(main())
