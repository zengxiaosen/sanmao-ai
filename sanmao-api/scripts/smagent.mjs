#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import http from 'node:http';
import https from 'node:https';
import readline from 'node:readline/promises';

const __filename = fileURLToPath(import.meta.url);
const scriptDir = path.dirname(__filename);

const MODEL_PRIORITY = [
  'glm-5.2', 'glm-5.1', 'glm-5',
  'qwen3.7-max', 'qwen3.7-plus',
  'deepseek-v4-pro', 'deepseek-v4-flash',
  'claude-opus-4-8', 'claude-opus-4-7', 'claude-opus-4-6',
  'claude-sonnet-4-6', 'claude-sonnet-4-5-20250929', 'claude-haiku-4-5-20251001',
  'gpt-5.5', 'gpt-5.4', 'gpt-5.4-mini', 'gpt-5.3-codex-spark', 'codex-auto-review',
];

function getLocalAppData() {
  return process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
}

function parseArgs(argv) {
  const options = {
    printEnv: false,
    skipTunnel: false,
    listModels: false,
    pickModel: false,
    sessionOnly: false,
    clearDefault: false,
    setup: false,
    rememberModel: false,
    model: '',
    claudeArgs: [],
  };

  let index = 0;
  let stopParsing = false;
  while (index < argv.length) {
    if (stopParsing) {
      options.claudeArgs.push(argv[index]);
      index += 1;
      continue;
    }

    const arg = argv[index];
    switch (arg) {
      case 'models':
        options.listModels = true;
        index += 1;
        break;
      case 'pick':
        options.pickModel = true;
        index += 1;
        break;
      case 'setup':
        options.setup = true;
        index += 1;
        break;
      case 'clear-default':
        options.clearDefault = true;
        index += 1;
        break;
      case '--print-env':
        options.printEnv = true;
        index += 1;
        break;
      case '--skip-tunnel':
        options.skipTunnel = true;
        index += 1;
        break;
      case '--list-models':
        options.listModels = true;
        index += 1;
        break;
      case '--pick-model':
        options.pickModel = true;
        index += 1;
        break;
      case '--session-only':
        options.sessionOnly = true;
        index += 1;
        break;
      case '--clear-default-model':
        options.clearDefault = true;
        index += 1;
        break;
      case '--remember-model':
        options.rememberModel = true;
        index += 1;
        break;
      case '--setup':
        options.setup = true;
        index += 1;
        break;
      case '--model':
        if (index + 1 >= argv.length) {
          throw new Error('[smagent] --model requires a value');
        }
        options.model = argv[index + 1];
        index += 2;
        break;
      case '--':
        stopParsing = true;
        index += 1;
        break;
      default:
        stopParsing = true;
        break;
    }
  }

  return options;
}

async function pathExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function readEnvToken(filePath) {
  if (!(await pathExists(filePath))) {
    return '';
  }
  const lines = (await fs.readFile(filePath, 'utf8')).split(/\r?\n/);
  for (const line of lines) {
    const match = line.match(/^\s*SANMAO_API_KEY=(.*)$/);
    if (match) {
      return match[1].trim();
    }
  }
  return '';
}

async function readLegacyPs1Token(filePath) {
  if (!(await pathExists(filePath))) {
    return '';
  }
  const lines = (await fs.readFile(filePath, 'utf8')).split(/\r?\n/);
  for (const line of lines) {
    const match = line.match(/^\$env:SANMAO_API_KEY="(.+)"$/);
    if (match) {
      return match[1];
    }
  }
  return '';
}

async function readFirstLine(filePath) {
  if (!(await pathExists(filePath))) {
    return '';
  }
  const text = await fs.readFile(filePath, 'utf8');
  return text.split(/\r?\n/)[0]?.trim() || '';
}

async function ensureDir(targetPath) {
  await fs.mkdir(targetPath, { recursive: true });
}

async function saveToken(configFile, token) {
  await fs.writeFile(configFile, `SANMAO_API_KEY=${token}\n`, 'utf8');
}

function requestText(url, headers, timeoutMs) {
  const client = url.startsWith('https:') ? https : http;
  return new Promise((resolve, reject) => {
    const req = client.request(url, { method: 'GET', headers }, (res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        body += chunk;
      });
      res.on('end', () => {
        if ((res.statusCode || 500) >= 400) {
          reject(new Error(`HTTP ${res.statusCode}: ${body}`));
          return;
        }
        resolve(body);
      });
    });
    req.on('error', reject);
    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error(`timeout after ${timeoutMs}ms`));
    });
    req.end();
  });
}

async function fetchModels(modelsUrl, token) {
  let body;
  try {
    body = await requestText(modelsUrl, {
      'x-api-key': token,
      'anthropic-version': '2023-06-01',
    }, 30000);
  } catch (error) {
    const message = String(error?.message || error);
    if (message.includes('HTTP 401')) {
      throw new Error('[smagent] token unauthorized. It may be disabled/expired, or the saved SANMAO_API_KEY is stale.\n[smagent] run smagent-setup with a fresh token, then retry.');
    }
    throw new Error(`[smagent] failed to fetch models: ${message}`);
  }
  const payload = JSON.parse(body);
  const ids = Array.isArray(payload.data)
    ? payload.data
        .filter((item) => item && typeof item === 'object' && item.id)
        .map((item) => item.id)
    : [];
  const ordered = MODEL_PRIORITY.filter((model) => ids.includes(model));
  const remaining = ids.filter((model) => !ordered.includes(model)).sort();
  return [...ordered, ...remaining];
}

async function promptText(label) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
    return (await rl.question(`${label} `)).trim();
  } finally {
    rl.close();
  }
}

function runCommandOrThrow(command, args, options = {}) {
  const result = spawnSync(command, args, {
    encoding: 'utf8',
    stdio: options.capture ? 'pipe' : 'inherit',
    shell: false,
    env: options.env || process.env,
    windowsHide: true,
  });
  if (result.error) {
    throw result.error;
  }
  if ((result.status ?? 1) !== 0) {
    if (options.capture) {
      if (result.stdout) process.stdout.write(result.stdout);
      if (result.stderr) process.stderr.write(result.stderr);
    }
    process.exit(result.status ?? 1);
  }
  return result;
}

function scriptCommandFor(targetPath) {
  const lower = targetPath.toLowerCase();
  if (lower.endsWith('.mjs')) {
    return { command: process.execPath, args: [targetPath] };
  }
  if (lower.endsWith('.py')) {
    return { command: 'python', args: [targetPath] };
  }
  if (lower.endsWith('.ps1')) {
    return { command: 'powershell.exe', args: ['-ExecutionPolicy', 'Bypass', '-File', targetPath] };
  }
  return { command: targetPath, args: [] };
}

async function ensureTunnel(skipTunnel, tunnelScript) {
  if (skipTunnel) {
    return;
  }
  if (!(await pathExists(tunnelScript))) {
    throw new Error(`[smagent] missing tunnel helper at ${tunnelScript}`);
  }
  const runner = scriptCommandFor(tunnelScript);
  runCommandOrThrow(runner.command, runner.args, { capture: true });
}

function classifyModelFamily(model) {
  const lowered = String(model || '').trim().toLowerCase();
  if (lowered.startsWith('gpt-') || lowered.startsWith('codex-')) {
    return 'codex';
  }
  return 'ccr';
}

function ensureCCR() {
  const probe = spawnSync('ccr', ['--help'], { encoding: 'utf8', stdio: 'pipe', windowsHide: true });
  if (probe.error || (probe.status ?? 1) !== 0) {
    throw new Error(`[smagent] ccr is not installed or not on PATH.\n[smagent] install Claude Code Router first, then configure it for your sanmao-backed Claude-compatible models.`);
  }
}

function ensureCodexProxy(scriptDir) {
  const proxyScript = process.env.SMAGENT_CODEX_PROXY_SCRIPT || path.join(scriptDir, 'start-codex-fallback-proxy.sh');
  runCommandOrThrow(proxyScript, [], { capture: true });
}

function runDispatchedBackend(model, extraArgs, env, rememberModel, sessionOnly, scriptDir) {
  const family = classifyModelFamily(model);
  console.error(`[smagent] launching model: ${model}`);
  console.error(`[smagent] selected backend family: ${family}`);
  if (rememberModel && !sessionOnly) {
    console.error('[smagent] remembering model for future launches');
  } else {
    console.error('[smagent] session-only model selection (not persisted)');
  }

  if (family === 'codex') {
    ensureCodexProxy(scriptDir);
    const child = spawn('codex', ['--model', model, ...extraArgs], { stdio: 'inherit', windowsHide: true });
    child.on('error', (error) => {
      console.error(error.message);
      process.exit(1);
    });
    child.on('exit', (code, signal) => {
      if (signal) {
        process.kill(process.pid, signal);
        return;
      }
      process.exit(code ?? 0);
    });
    return;
  }

  ensureCCR();
  const child = spawn('ccr', ['code', '--', '--model', model, ...extraArgs], { stdio: 'inherit', env, windowsHide: true });
  child.on('error', (error) => {
    console.error(error.message);
    process.exit(1);
  });
  child.on('exit', (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 0);
  });
}

async function pickModel(currentModel, models) {
  if (!models.length) {
    throw new Error('[smagent] no models available from sanmao');
  }
  console.log('Available sanmao-backed gateway models:');
  models.forEach((model, index) => {
    const marker = currentModel && model === currentModel ? ' *' : '  ';
    console.log(`${String(index + 1).padStart(2, ' ')}.${marker} ${model}`);
  });
  console.log('');
  const choice = await promptText('Model');
  if (!choice) {
    throw new Error('[smagent] model selection cancelled');
  }
  if (/^\d+$/.test(choice)) {
    const selectedIndex = Number(choice) - 1;
    if (selectedIndex >= 0 && selectedIndex < models.length) {
      return models[selectedIndex];
    }
    throw new Error('[smagent] invalid selection');
  }
  if (models.includes(choice)) {
    return choice;
  }
  const matches = models.filter((model) => model.toLowerCase().includes(choice.toLowerCase()));
  if (matches.length === 1) {
    return matches[0];
  }
  if (matches.length > 1) {
    throw new Error(`[smagent] ambiguous match: ${matches.join(', ')}`);
  }
  throw new Error('[smagent] model not found');
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const installRoot = process.env.SANMAO_CLAUDE_ROOT || path.join(getLocalAppData(), 'smagent');
  const configDir = process.env.SANMAO_CLAUDE_CONFIG_DIR || path.join(installRoot, 'config');
  const stateDir = process.env.SANMAO_CLAUDE_STATE_DIR || path.join(installRoot, 'state');
  const legacyStateDir = path.join(os.homedir(), '.config', 'smagent');
  const tunnelScript = process.env.SANMAO_START_TUNNEL_SCRIPT || path.join(configDir, 'start-local-tunnel.mjs');
  const baseUrl = process.env.SANMAO_CLAUDE_BASE_URL || 'https://www.sanmao.fun';
  const modelsUrl = process.env.SANMAO_CLAUDE_MODELS_URL || `${baseUrl}/v1/models`;
  const defaultModelFile = path.join(stateDir, 'default-model');
  const configFile = path.join(stateDir, 'config.env');
  const legacyDefaultModelFile = path.join(legacyStateDir, 'default-model');
  const legacyConfigFile = path.join(legacyStateDir, 'config.env');
  const legacyPs1ConfigFile = path.join(legacyStateDir, 'config.ps1env');

  await ensureDir(stateDir);

  let token = process.env.SANMAO_API_KEY
    || process.env.ANTHROPIC_API_KEY_SM
    || process.env.ANTHROPIC_AUTH_TOKEN_SM
    || process.env.ANTHROPIC_API_KEY
    || '';

  if (!token) {
    token = await readEnvToken(configFile)
      || await readEnvToken(legacyConfigFile)
      || await readLegacyPs1Token(legacyPs1ConfigFile);
  }

  if (options.setup) {
    if (!token) {
      token = await promptText('Enter sanmao API key:');
    }
    if (!token) {
      throw new Error('[smagent] no API key provided');
    }
    await saveToken(configFile, token);
    console.log(`[smagent] saved token to ${configFile}`);
    return;
  }

  if (!token) {
    throw new Error(`[smagent] missing SANMAO_API_KEY, ANTHROPIC_API_KEY_SM, or stored config at ${configFile}`);
  }

  if (options.clearDefault) {
    await fs.rm(defaultModelFile, { force: true });
    await fs.rm(legacyDefaultModelFile, { force: true });
  }

  await ensureTunnel(options.skipTunnel, tunnelScript);

  const currentDefault = await readFirstLine(defaultModelFile) || await readFirstLine(legacyDefaultModelFile);

  if (options.printEnv) {
    console.log(`ANTHROPIC_BASE_URL=${baseUrl}`);
    console.log('ANTHROPIC_API_KEY is set');
    console.log('ANTHROPIC_AUTH_TOKEN is unset');
    if (currentDefault) {
      console.log(`DEFAULT_MODEL=${currentDefault}`);
    } else {
      console.log('DEFAULT_MODEL is not set');
    }
    console.log(`CONFIG_FILE=${configFile}`);
    return;
  }

  const runtimeEnv = {
    ...process.env,
    ANTHROPIC_API_KEY: token,
    ANTHROPIC_BASE_URL: baseUrl,
  };
  delete runtimeEnv.ANTHROPIC_AUTH_TOKEN;

  if (options.listModels) {
    const models = await fetchModels(modelsUrl, token);
    models.forEach((model) => console.log(model));
    return;
  }

  let selectedModel = options.model || '';
  let shouldPick = options.pickModel;
  if (!selectedModel && !shouldPick && options.claudeArgs.length === 0 && !currentDefault) {
    shouldPick = true;
  }

  if (shouldPick) {
    const models = await fetchModels(modelsUrl, token);
    selectedModel = await pickModel(currentDefault, models);
  } else if (!selectedModel && currentDefault) {
    selectedModel = currentDefault;
  }

  if (selectedModel && options.rememberModel && !options.sessionOnly) {
    await fs.writeFile(defaultModelFile, `${selectedModel}\n`, 'utf8');
  }

  runDispatchedBackend(selectedModel, options.claudeArgs, runtimeEnv, options.rememberModel, options.sessionOnly, scriptDir);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
