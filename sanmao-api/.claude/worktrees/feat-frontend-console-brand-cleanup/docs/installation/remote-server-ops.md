# Remote Server Operations: sanmao-api

Last updated: 2026-06-18

This document captures the currently verified remote deployment topology and rollout guidance for the live `sanmao-api` environment, so future server checks and releases do not have to rediscover the same facts through ad-hoc SSH inspection.

Sensitive values such as API keys and tokens are intentionally omitted.

Related docs:

- `docs/installation/server-state-2026-05-18.md`
- `docs/installation/migration-checklist.md`
- `docs/installation/database-verification.md`
- `docs/channel/claude-channel-routing.md`

## Primary remote host

- Host used for recent production inspection: `root@120.24.144.153`

## Relevant services on the host

Two relevant systemd services are currently present:

### 1. `sanmao-api.service`

This is the Go gateway service for this repo.

Current verified shape:

```ini
[Unit]
Description=Sanmao API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/sanmao/sanmao-api
ExecStart=/opt/sanmao/sanmao-api/new-api --port 3000 --log-dir /opt/sanmao/sanmao-api/logs
Restart=always
RestartSec=5
Environment=GIN_MODE=release

[Install]
WantedBy=multi-user.target
```

### 2. `sanmao.service`

This is a separate Python/SQLite app and is not the Go gateway being modified for model/provider support work.

Verified shape summary:

- working directory: `/var/www/sanmao/server`
- entrypoint: `/usr/bin/python3 /var/www/sanmao/server/app.py`
- environment includes:
  - `SANMAO_DB_PATH=/var/www/sanmao/server/data/sanmao.db`
  - `SANMAO_STATIC_ROOT=/var/www/sanmao`
  - `SANMAO_API_PORT=8000`

## Remote app layout for the Go gateway

Under `/opt/sanmao/sanmao-api` we verified:

- it is a git repo, not only a binary drop
- deployed binary: `new-api`
- working tree includes source code
- live SQLite database: `one-api.db`
- service log directory: `logs/`

Operational consequence:

- production support state depends on both deployed code and DB contents
- server inspection should not stop at `git rev-parse` or `systemctl status`

## Why code changes alone are not enough

For this repo, a provider or model may be supported in code but still not effectively usable in production because the remote DB can lag behind.

The most important remote tables/keys to inspect are:

### `channels`

High-value columns:

- `id`
- `name`
- `type`
- `status`
- `base_url`
- `models`
- `model_mapping`
- `header_override`
- `settings`

Reason:
- actual provider/model enablement lives here
- model support can exist in code but still be absent from configured channels

### `options`

High-value keys:

- `ModelRatio`
- `CompletionRatio`
- `CacheRatio`

Reason:
- DB overrides can shadow new code defaults
- newly added model IDs may still be filtered, billed incorrectly, or behave inconsistently if these rows are stale

## Recently verified model-support snapshot

During the latest inspection of `120.24.144.153`:

- the primary production provider channel for this work is still the Ali channel `aliyun-token-plan` (`type = 17`)
- no active `Zhipu` / `ZhipuV4` channels were present in the inspected DB state
- after deploying the local model-support patch and updating the remote DB, the effective Ali-backed production model set now includes:
  - `qwen3.7-plus`
  - `qwen3.7-plus-2026-05-26`
  - `qwen3.7-max`
  - `qwen3.7-max-2026-06-08`
  - `deepseek-v4-pro`
  - `deepseek-v4-flash`
  - `glm-5`
  - `glm-5.1`
  - `glm-5.2`
- `options.ModelRatio` / `CompletionRatio` / `CacheRatio` were also updated remotely to keep those models visible and billable

Operational consequence:

- Qwen support is currently active through Ali
- DeepSeek support is currently active through Ali
- `glm-5`, `glm-5.1`, and `glm-5.2` are currently usable through the same Ali token-plan channel
- this is an operationally valid setup for the current environment, even though it is not a dedicated `ZhipuV4` production channel yet

### Important model admission rule for the current Ali-backed GLM setup

Do not expose a GLM model to production only because it appears in provider docs or in a static constant list.

For the current Ali-backed path, a GLM model should be added to production `channels.models` and `abilities` only if **both** are true:

1. the Ali upstream model list actually returns the model ID
2. a real relay request against the current Ali upstream succeeds

This rule matters because some GLM-family IDs may look nominally supported in code but still fail on the current upstream route.

### Current validated GLM status on Ali token-plan

Validated usable now:

- `glm-5`
- `glm-5.1`
- `glm-5.2`

Do not expose on the current Ali-backed production path unless upstream behavior changes:

- `glm-5v-turbo`
- `glm-4.1v-thinking-flashx`

Reason:

- these returned `404` during direct upstream verification on the current Ali token-plan route, so exposing them would create false-positive model availability

## Recommended workflow for future rollout work

### Phase A — local repository work first

Before touching the server:

1. finish local code changes
2. add/update tests
3. format changes
4. run the relevant local verification if toolchain/network permits
5. review the exact diff to avoid bundling unrelated in-progress work
6. commit locally before remote rollout

### Phase B — map local changes to remote follow-up

Use this checklist:

- **provider/model constants changed?**
  - deploy updated code/binary
- **pricing defaults changed?**
  - inspect remote `options.ModelRatio`, `CompletionRatio`, `CacheRatio`
- **new model IDs added?**
  - update `channels.models` or trigger upstream model sync
- **new provider should become usable in production?**
  - add/create the corresponding channel, e.g. `ZhipuV4`
- **upstream fetch logic changed?**
  - verify the real remote channel can fetch models from the correct provider-specific endpoint

### Phase C — remote verification after rollout

Recommended order:

1. `systemctl status sanmao-api.service`
2. verify deployed revision and working tree under `/opt/sanmao/sanmao-api`
3. inspect `one-api.db` for the relevant `channels` and `options` rows
4. verify model fetch/sync behavior
5. verify user-visible model exposure if applicable
6. restart the service only after code and DB/config are aligned

## Current guidance for Qwen / GLM / DeepSeek support work

For the current model-support patch series, after local changes are committed and deployed, the expected remote follow-up is:

1. deploy updated code/binary to `/opt/sanmao/sanmao-api`
2. inspect remote `options.ModelRatio`, `CompletionRatio`, and `CacheRatio` for overrides that might shadow the new defaults
3. update the Ali channel model list to include any newly exposed Qwen / DeepSeek IDs
4. add a `ZhipuV4` channel if GLM support is intended to become active remotely
5. restart `sanmao-api.service`
6. verify the server returns the new models and routes them correctly

## Documentation rule

When a new stable deployment fact is learned:

- update this document if it is reusable operational knowledge
- update `docs/installation/server-state-2026-05-18.md` if the broader machine state changed
- keep the local `.claude/skills/remote-server-ops/SKILL.md` in sync for Claude-side operational reuse

Do not leave important remote deployment knowledge only in chat history.
