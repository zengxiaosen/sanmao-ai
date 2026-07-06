#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { spawn, spawnSync } from 'node:child_process';
import http from 'node:http';

function requestOk(url, timeoutMs) {
  return new Promise((resolve) => {
    const req = http.request(url, { method: 'GET' }, (res) => {
      res.resume();
      resolve((res.statusCode || 500) < 400);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(timeoutMs, () => {
      req.destroy();
      resolve(false);
    });
    req.end();
  });
}

function isPidRunning(pid) {
  if (!pid) {
    return false;
  }
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function pathExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function readPid(pidPath) {
  if (!(await pathExists(pidPath))) {
    return 0;
  }
  return Number((await fs.readFile(pidPath, 'utf8')).trim()) || 0;
}

function runCapture(command, args) {
  return spawnSync(command, args, {
    encoding: 'utf8',
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
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

function killPid(pid) {
  if (!pid) {
    return;
  }
  runCapture('taskkill', ['/PID', String(pid), '/F', '/T']);
}

async function main() {
  const listenHost = process.env.SANMAO_TUNNEL_HOSTNAME || '127.0.0.1';
  const listenPort = Number(process.env.SANMAO_TUNNEL_PORT || '13000');
  const remoteHost = process.env.SANMAO_TUNNEL_HOST || 'root@120.24.144.153';
  const remoteTarget = process.env.SANMAO_TUNNEL_TARGET || '127.0.0.1:3000';
  const pidPath = process.env.SANMAO_TUNNEL_PID || path.join(os.homedir(), '.ssh', 'sanmao-tunnel.pid');
  const healthUrl = process.env.SANMAO_TUNNEL_HEALTH_URL || `http://${listenHost}:${listenPort}/api/status`;

  const existingPid = await readPid(pidPath);
  if (existingPid && !isPidRunning(existingPid)) {
    await fs.rm(pidPath, { force: true });
  }

  const healthyPid = await readPid(pidPath);
  if (healthyPid && isPidRunning(healthyPid) && await requestOk(healthUrl, 3000)) {
    console.log(`[tunnel] already running: pid=${healthyPid}`);
    console.log(`[tunnel] health check ok: ${healthUrl}`);
    return;
  }

  for (const pid of listenerPids(listenPort)) {
    killPid(pid);
    console.log(`[tunnel] removed listener pid=${pid}`);
  }

  await fs.mkdir(path.dirname(pidPath), { recursive: true });

  const sshArgs = [
    '-o', 'ExitOnForwardFailure=yes',
    '-o', 'ServerAliveInterval=30',
    '-o', 'ServerAliveCountMax=3',
    '-N',
    '-L', `${listenHost}:${listenPort}:${remoteTarget}`,
    remoteHost,
  ];

  console.log(`[tunnel] opening ${listenHost}:${listenPort} -> ${remoteTarget} via ${remoteHost}`);
  const proc = spawn('ssh', sshArgs, {
    detached: true,
    stdio: 'ignore',
    windowsHide: true,
  });
  proc.unref();
  await fs.writeFile(pidPath, `${proc.pid}\n`, 'utf8');

  for (let attempt = 0; attempt < 5; attempt += 1) {
    if (await requestOk(healthUrl, 3000)) {
      console.log(`[tunnel] ready: pid=${proc.pid}`);
      console.log(`[tunnel] health check ok: ${healthUrl}`);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  killPid(proc.pid);
  throw new Error(`[tunnel] failed health check: ${healthUrl}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
