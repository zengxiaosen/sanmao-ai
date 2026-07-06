#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def request_ok(url: str, timeout: float) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status < 400
    except Exception:
        return False


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_pid(pid_path: Path) -> int:
    if not pid_path.exists():
        return 0
    try:
        return int(pid_path.read_text(encoding='utf-8').strip())
    except Exception:
        return 0


def listener_pids(port: int) -> list[int]:
    result = subprocess.run(
        ['netstat', '-ano', '-p', 'tcp'],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    pids: set[int] = set()
    for raw_line in result.stdout.splitlines():
        parts = raw_line.split()
        if len(parts) < 5 or parts[0].upper() != 'TCP':
            continue
        local_address = parts[1]
        state = parts[3].upper()
        try:
            pid = int(parts[4])
        except ValueError:
            continue
        if state != 'LISTENING' or pid <= 0:
            continue
        if local_address.endswith(f':{port}'):
            pids.add(pid)
    return list(pids)


def kill_pid(pid: int) -> None:
    if pid <= 0:
        return
    subprocess.run(['taskkill', '/PID', str(pid), '/F', '/T'], check=False, capture_output=True, text=True)


def main() -> int:
    listen_host = os.environ.get('SANMAO_TUNNEL_HOSTNAME', '127.0.0.1')
    listen_port = int(os.environ.get('SANMAO_TUNNEL_PORT', '13000'))
    remote_host = os.environ.get('SANMAO_TUNNEL_HOST', 'root@120.24.144.153')
    remote_target = os.environ.get('SANMAO_TUNNEL_TARGET', '127.0.0.1:3000')
    pid_path = Path(os.environ.get('SANMAO_TUNNEL_PID', str(Path.home() / '.ssh' / 'sanmao-tunnel.pid')))
    health_url = os.environ.get('SANMAO_TUNNEL_HEALTH_URL', f'http://{listen_host}:{listen_port}/api/status')

    pid_value = read_pid(pid_path)
    if pid_value and not is_pid_running(pid_value):
        pid_path.unlink(missing_ok=True)

    healthy_pid = read_pid(pid_path)
    if healthy_pid and is_pid_running(healthy_pid) and request_ok(health_url, 3):
        print(f'[tunnel] already running: pid={healthy_pid}')
        print(f'[tunnel] health check ok: {health_url}')
        return 0

    for listener_pid in listener_pids(listen_port):
        kill_pid(listener_pid)
        print(f'[tunnel] removed listener pid={listener_pid}')

    pid_path.parent.mkdir(parents=True, exist_ok=True)

    ssh_args = [
        'ssh',
        '-o', 'ExitOnForwardFailure=yes',
        '-o', 'ServerAliveInterval=30',
        '-o', 'ServerAliveCountMax=3',
        '-N',
        '-L', f'{listen_host}:{listen_port}:{remote_target}',
        remote_host,
    ]
    print(f'[tunnel] opening {listen_host}:{listen_port} -> {remote_target} via {remote_host}')
    creationflags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    proc = subprocess.Popen(ssh_args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
    pid_path.write_text(f'{proc.pid}\n', encoding='utf-8')

    for _ in range(5):
        if request_ok(health_url, 3):
            print(f'[tunnel] ready: pid={proc.pid}')
            print(f'[tunnel] health check ok: {health_url}')
            return 0
        time.sleep(1)

    kill_pid(proc.pid)
    raise SystemExit(f'[tunnel] failed health check: {health_url}')


if __name__ == '__main__':
    raise SystemExit(main())
