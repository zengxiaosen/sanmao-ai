# Local Claude and Codex Integration with sanmao-api

Last updated: 2026-05-29

This guide explains how to make a local `Claude Code` client and a local `Codex` client use your deployed `sanmao-api` as the single upstream entrypoint.

It is written for the current live deployment shape:

- Host: `root@120.24.144.153`
- Public URL: `https://www.sanmao.fun`
- App root: `/opt/sanmao/sanmao-api`
- Local SSH login: passwordless login already configured from this machine

## What already works in `sanmao-api`

The current codebase already supports the two protocol shapes you need:

- Claude-compatible requests on `POST /v1/messages`
- OpenAI Responses-compatible requests on `POST /v1/responses`

Relevant code:

- `router/relay-router.go`
- `relay/claude_handler.go`
- `relay/channel/codex/adaptor.go`

That means you do not need a brand new gateway implementation. The practical work is:

1. Deploy `sanmao-api`
2. Add upstream channels in the admin console
3. Create one local token for your machine
4. Point local Claude and Codex to the same public base URL

## Recommended topology

Use `sanmao-api` as the public gateway, and keep the real upstream providers hidden behind channel configuration.

Recommended client mapping:

- Claude Code
  - Base URL: `https://www.sanmao.fun`
  - API key: your `sanmao-api` token
  - Endpoint shape used by client: `/v1/messages`

- Codex CLI
  - Base URL: `https://www.sanmao.fun/v1`
  - API key: your `sanmao-api` token
  - Wire API: `responses`
  - Endpoint shape used by client: `/v1/responses`

## Server-side prerequisites

Before changing local clients, make sure the server has:

1. A working public HTTPS domain
2. One enabled token for your local machine
3. At least one enabled Claude channel
4. At least one enabled Codex/OpenAI Responses channel

## Claude channel expectations

For Claude-compatible local clients, requests arrive as:

- `POST /v1/messages`
- `x-api-key: <sanmao token>`
- `anthropic-version: 2023-06-01` or a newer supported version

`sanmao-api` already maps `x-api-key` into internal token auth and then relays to the configured Claude-style upstream.

Recommended channel setup:

- Channel type: Anthropic
- Model list: only the Claude models you actually want exposed
- Base URL: your real upstream Claude-compatible provider

## Codex channel expectations

For the current local Codex CLI on this machine, the active config is OpenAI Responses mode, not Chat Completions mode.

The important local behavior is:

- provider name: `codex`
- `wire_api = "responses"`
- requests go to `/v1/responses`
- auth is sent as an OpenAI-style bearer key

`sanmao-api` already contains a Codex-specific adaptor for `/v1/responses` and `/v1/responses/compact`.

Important limitation:

- the `codex` channel type in this repo expects the upstream API key to be a JSON object containing fields such as `access_token` and `account_id`
- this is for relaying to ChatGPT/Codex-style backend APIs such as `/backend-api/codex/responses`

So you have two valid ways to use local Codex through `sanmao-api`:

### Option A: easiest and recommended

Treat local Codex as just another OpenAI Responses client.

Use an OpenAI-compatible upstream channel behind `sanmao-api`, for example:

- OpenAI-compatible provider
- OpenRouter-like provider
- your own Responses-capable upstream

In this mode:

- local Codex talks to `sanmao-api`
- `sanmao-api` authenticates with your own token
- `sanmao-api` then routes to an OpenAI-compatible upstream channel

This is operationally simpler than using the repo's dedicated `codex` channel type.

### Option B: dedicated Codex backend relay

Use the repo's `codex` channel type only if your upstream is truly a Codex backend that requires:

- `Authorization: Bearer <access_token>`
- `chatgpt-account-id: <account_id>`
- path `/backend-api/codex/responses`

If your upstream does not look like that, do not use the dedicated `codex` channel type.

## Local Codex configuration on this machine

Current local file:

- `/Users/minwoo/.codex/config.toml`

Recommended stable shape on this machine:

```toml
[model_providers.codex]
name = "codex"
base_url = "http://127.0.0.1:13100/v1"
wire_api = "responses"
requires_openai_auth = true
```

Reason:

- `127.0.0.1:13100` is a local fallback proxy dedicated to Codex traffic
- when the SSH tunnel on `127.0.0.1:13000` is healthy, the proxy forwards to the tunnel
- when the tunnel is unavailable, the proxy automatically falls back to the public `https://www.sanmao.fun/v1`
- this avoids depending on the local Codex client's own flaky direct TLS path to `www.sanmao.fun`

And set the local auth file to your `sanmao-api` token:

File:

- `/Users/minwoo/.codex/auth.json`

Example:

```json
{
  "OPENAI_API_KEY": "sk-your-sanmao-token"
}
```

## Local Claude configuration on this machine

This machine is currently launching Claude Code with Anthropic-compatible environment variables.

The stable direct tunnel form is:

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:13000"
export ANTHROPIC_API_KEY="sk-your-sanmao-token"
```

For a better day-to-day UX on any machine, use the installer once, then the short commands:

```bash
chmod +x scripts/install-smclaude.sh
bash scripts/install-smclaude.sh
smclaude-setup
smclaude
```

This launcher gives you the practical UX that Claude Code's built-in `/model` picker does not:

- it starts the local tunnel first unless you explicitly skip it
- it forces the launched Claude process to use only the sanmao API-key route (no `ANTHROPIC_AUTH_TOKEN` conflict)
- it shows the current sanmao-backed model list before launch
- it lets you choose a model and then launches `claude --model <that-model>`
- it remembers the chosen model in `~/.config/sanmao-claude/default-model`

Common usage patterns:

```bash
# One-time setup: install the user-level launcher stack and save the sanmao token
bash scripts/install-smclaude.sh
smclaude-setup

# Show the current sanmao-backed model list
smclaude-models

# Interactively choose a model, then launch Claude
smclaude-pick

# Launch directly with an explicit model
smclaude --model glm-5.2

# Clear the remembered default model
~/.npm-global/bin/claude-sanmao clear-default
```

For even shorter commands on this machine, three PATH shortcuts are available:

```bash
smclaude-models
smclaude --model glm-5.2
smclaude-pick
```

Behavior:

- by default it starts the local SSH tunnel first
- it then sets `ANTHROPIC_BASE_URL=http://127.0.0.1:13000`
- it loads the sanmao token from `SANMAO_API_KEY`, `ANTHROPIC_API_KEY_SM`, `ANTHROPIC_AUTH_TOKEN_SM`, or `~/.config/sanmao-claude/config.env`
- it explicitly unsets `ANTHROPIC_AUTH_TOKEN` for that launched Claude process, so Claude Code does not warn about conflicting auth sources
- if you pick or pass a model, it launches `claude --model <that-model>`
- it remembers the chosen model unless you use `--session-only`
- it does not modify your global Claude configuration; it only affects the launched process

If you want a simpler wrapper that just launches Claude through sanmao without model picking, you can still use:

```bash
chmod +x scripts/run-claude-via-sanmao.sh
SANMAO_API_KEY="sk-your-sanmao-token" bash scripts/run-claude-via-sanmao.sh
```

For debugging only, you can inspect the exported values without launching Claude:

```bash
~/.npm-global/bin/claude-sanmao --print-env
```

Why this route is practical:

- the current sanmao `/v1/messages` path was verified not only for Claude models, but also for `qwen3.7-max`, `deepseek-v4-pro`, and `glm-5.2`
- unlike Codex, Claude-style traffic can already reach these models through the existing `/v1/messages` compatibility path
- Claude Code's built-in `/model` picker does **not** dynamically mirror arbitrary gateway-exposed models, so the sanmao launcher provides the missing model-list and model-selection UX outside Claude Code itself
- this avoids building a fragile Codex-specific responses-to-chat bridge that could be overwritten or invalidated by future Codex client changes

If the local launcher already exports `ANTHROPIC_BASE_URL` to another domain, replace it for that process only via this wrapper or temporary shell exports.

Do not append `/v1/messages` manually. The client should use the base URL and attach its own endpoint path.

## Suggested first-pass model exposure

Keep the public model list small at the beginning.

Recommended initial models:

- Claude:
  - `claude-sonnet-4-5-20250929`
  - `claude-opus-4-5-20251101`

- Codex / Responses:
  - `gpt-5.4`
  - `gpt-5.5`
  - `gpt-5.4-mini`
  - `gpt-5.3-codex-spark`
  - `codex-auto-review`

Reason:

- easier routing validation
- clearer quota attribution
- lower chance of clients picking an unsupported model name

Do not expose model names in `sanmao-api` that the real upstream key does not
return from `/v1/models`. In the current live `vision-codex` setup, this means
you should not advertise `gpt-5-codex` or `gpt-5.1-codex*` unless the upstream
provider key actually gains those models later.

## Fallback for Macs with ClashX and Cisco AnyConnect

If your Mac cannot reach `https://www.sanmao.fun` reliably because a local proxy stack or a Cisco AnyConnect socket filter is interfering with outbound TLS, do not keep fighting the public `443` path.

Use a local SSH tunnel to the Alibaba Cloud host instead.

### Why this fallback is recommended

On the current machine, the following combination exists at the same time:

- `ClashX` local proxy on `127.0.0.1:7890`
- `Cisco AnyConnect Socket Filter Extension`

This is enough to create cases where:

- public `https://www.sanmao.fun` resets locally
- requests do not show up in Clash logs
- turning Clash off breaks other required connectivity

An SSH local port forward avoids that path completely while still sending all Claude/Codex traffic through your own `sanmao-api`.

### Start the tunnel

From the repo root:

```bash
chmod +x scripts/start-local-tunnel.sh scripts/stop-local-tunnel.sh
bash scripts/start-local-tunnel.sh
```

The tunnel now runs as a single background SSH process tracked by:

- `~/.ssh/sanmao-tunnel.pid`

`start-local-tunnel.sh` is idempotent:

- if a healthy tunnel already exists, it exits successfully without starting another one
- if a stale listener is occupying `127.0.0.1:13000`, it cleans it up and recreates the tunnel
- after startup, it checks `http://127.0.0.1:13000/api/status`

Default mapping:

- local `127.0.0.1:13000`
- remote `127.0.0.1:3000`

Quick check:

```bash
curl http://127.0.0.1:13000/api/status
```

### Point local Codex to the fallback proxy

Recommended stable setup:

```toml
[model_providers.codex]
name = "codex"
base_url = "http://127.0.0.1:13100/v1"
wire_api = "responses"
requires_openai_auth = true
```

Behavior:

- if `127.0.0.1:13000` is healthy, the fallback proxy automatically uses the tunnel upstream
- if `127.0.0.1:13000` is unavailable, the fallback proxy automatically uses the public `https://www.sanmao.fun/v1`
- you do not need to edit Codex config when the tunnel appears or disappears

### Point local Claude to the tunnel

Use:

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:13000"
export ANTHROPIC_API_KEY="sk-your-sanmao-token"
```

### Stop the tunnel

```bash
bash scripts/stop-local-tunnel.sh
```

### Run the tunnel as a persistent macOS LaunchAgent

For automatic startup and restart after disconnects:

```bash
chmod +x scripts/install-launchd-tunnel.sh scripts/uninstall-launchd-tunnel.sh
bash scripts/install-launchd-tunnel.sh
```

This installs:

- `~/Library/LaunchAgents/com.minwoo.sanmao-tunnel.plist`

The agent runs:

- `/usr/bin/ssh -N -L 127.0.0.1:13000:127.0.0.1:3000 root@120.24.144.153`

and keeps it alive with `launchd`.

To remove it:

```bash
bash scripts/uninstall-launchd-tunnel.sh
```

If Claude fails with `ConnectionRefused`, check:

```bash
lsof -nP -iTCP:13000 -sTCP:LISTEN
curl http://127.0.0.1:13000/api/status
```

## Operational improvements recommended before broad local cutover

These are the highest-value improvements for your use case.

### 1. Prefer OpenAI-compatible upstream for local Codex

This is the main practical recommendation.

The local Codex CLI on this machine is already happy with:

- OpenAI-style bearer key
- Responses API
- `/v1` base URL

So let `sanmao-api` expose a stable `/v1/responses` surface, and keep the upstream complexity inside channel routing.

### 2. Keep one token per machine

Do not reuse the same token across every desktop and script.

Create a dedicated token for:

- this MacBook
- CI jobs
- any remote automation

That gives you cleaner audit and easier rollback.

### 3. Use a dedicated group for local developer traffic

Create a group such as `local-dev` and bind the token to it.

Benefits:

- isolate rate limits
- isolate model exposure
- isolate billing/debugging

### 4. Add a small smoke test after each deploy

At minimum, test:

- `POST /v1/messages`
- `POST /v1/responses`
- `GET /v1/models`

For the current Ali-backed GLM path, also apply this model admission rule before exposing a new GLM ID to Codex or other local clients:

1. confirm the Ali upstream model list actually returns the model ID
2. send a real relay request through the current production path
3. only then add it to production `channels.models` / `abilities`

Current verified usable GLM IDs on this setup:

- `glm-5`
- `glm-5.1`
- `glm-5.2`

Current verified non-usable GLM IDs on this setup:

- `glm-5v-turbo`
- `glm-4.1v-thinking-flashx`

This avoids exposing a model that looks supported in docs or code constants but still returns `404` on the actual upstream route.

## Minimal smoke tests

### Claude-style test

```bash
curl https://www.sanmao.fun/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: sk-your-sanmao-token" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet-4-5-20250929",
    "max_tokens": 64,
    "messages": [{"role":"user","content":"say hi"}]
  }'
```

### Codex / Responses-style test

```bash
curl https://www.sanmao.fun/v1/responses \
  -H "content-type: application/json" \
  -H "authorization: Bearer sk-your-sanmao-token" \
  -d '{
    "model": "gpt-5.4",
    "input": "say hi"
  }'
```

## What is not worth changing yet

Do not start by rewriting Claude or Codex relay internals.

For your immediate goal, the repo already has the important transport surface. What matters first is:

- stable server deployment
- clean token strategy
- correct local base URLs
- verified upstream channel mapping

Only patch relay code after a real client request shows a protocol mismatch.
