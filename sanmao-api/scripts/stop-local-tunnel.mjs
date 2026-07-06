#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { spawnSync } from 'node:child_process';

function runCapture(command, args) {
  return spawnSync(command, args, {
    encoding: 'utf8',
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
}

function killPid(pid) {
  if (!pid) {
    return;
  }
  runCapture('taskkill', ['/PID', String(pid), '/F', '/T']);
}

function listenerPids(port) {
  const result = runCapture('netstat', ['-ano', '-p', 'tcp']);
  if (result.error || (result.status ?? 1) !== 0) {
    return [];
  }
  const pids = new Set();
  for (const line of result.stdout.split(/\r?\n/)) {
    const parts = line.trim().split(/\s+/);
    if (parts.length < 5 || parts[0].toUpperCase() !== 'TCP') {
      continue;
    }
    const localAddress = parts[1];
    const state = parts[3].toUpperCase();
    const pid = Number(parts[4]);
    if (state !== 'LISTENING' || !pid) {
      continue;
    }
    if (localAddress.endsWith(`:${port}`)) {
      pids.add(pid);
    }
  }
  return [...pids];
}

async function main() {
  const listenPort = Number(process.env.SANMAO_TUNNEL_PORT || '13000');
  const pidPath = process.env.SANMAO_TUNNEL_PID || path.join(os.homedir(), '.ssh', 'sanmao-tunnel.pid');

  try {
    const pid = Number((await fs.readFile(pidPath, 'utf8')).trim()) || 0;
    if (pid) {
      killPid(pid);
      console.log(`[tunnel] stopped pid=${pid}`);
    }
  } catch {
  }

  await fs.rm(pidPath, { force: true });

  for (const pid of listenerPids(listenPort)) {
    killPid(pid);
    console.log(`[tunnel] removed listener pid=${pid}`);
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
