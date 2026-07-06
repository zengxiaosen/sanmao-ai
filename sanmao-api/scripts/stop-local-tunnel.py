#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path


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
    listen_port = int(os.environ.get('SANMAO_TUNNEL_PORT', '13000'))
    pid_path = Path(os.environ.get('SANMAO_TUNNEL_PID', str(Path.home() / '.ssh' / 'sanmao-tunnel.pid')))

    try:
        pid_value = int(pid_path.read_text(encoding='utf-8').strip())
    except Exception:
        pid_value = 0

    if pid_value:
        kill_pid(pid_value)
        print(f'[tunnel] stopped pid={pid_value}')

    pid_path.unlink(missing_ok=True)

    for listener_pid in listener_pids(listen_port):
        kill_pid(listener_pid)
        print(f'[tunnel] removed listener pid={listener_pid}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
