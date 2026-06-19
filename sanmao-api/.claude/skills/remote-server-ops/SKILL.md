---
name: remote-server-ops
description: Track this repo's remote deployment topology, sanmao-api service layout, update flow, and safe server-side follow-up steps after local changes land.
---

# remote-server-ops

## What this skill is for

Use this skill for **this repo's remote deployment and server operations knowledge** so the same SSH exploration does not have to be rediscovered every time.

It is specifically for:

- understanding where `sanmao-api` is deployed on the remote host
- checking service/process status before or after a release
- mapping local code/config changes to the required remote follow-up
- inspecting channel/model/rate settings on the server
- recording deployment facts back into repo docs or project memory

This skill is about **operational knowledge reuse**, not arbitrary server hacking.

## When to use it

Use this skill when the task involves any of these:

1. "SSH in and check the deployed sanmao-api"
2. "Confirm whether the remote server supports a model/provider/config"
3. "Figure out where this service is running and how it starts"
4. "After local code changes, tell me what still needs to be changed on the server"
5. "Document what we learned about this server/deployment"
6. "Prepare rollout or verification steps for 120.24.144.153"

## Current known deployment facts

These are the currently verified facts for this project's main remote host.

### Host

- Primary server checked so far: `root@120.24.144.153`

### Services

Two relevant systemd services exist on that machine:

1. `sanmao-api.service`
   - binary service for this Go gateway
   - working directory: `/opt/sanmao/sanmao-api`
   - exec:
     - `/opt/sanmao/sanmao-api/new-api --port 3000 --log-dir /opt/sanmao/sanmao-api/logs`
   - environment:
     - `GIN_MODE=release`

2. `sanmao.service`
   - separate Python/SQLite app
   - not the Go gateway we were modifying
   - working directory: `/var/www/sanmao/server`

### Remote app layout for sanmao-api

Under `/opt/sanmao/sanmao-api` we already verified:

- it is a git repo
- deployed binary: `new-api`
- database file: `one-api.db`
- service logs dir: `logs/`
- repo contains source tree and checked-out code, not just compiled artifact

### Current deployed model/channel snapshot we observed

At the time of the latest verification:

- the primary relevant production channel is still the Ali channel `aliyun-token-plan` (`type = 17`)
- there are still no active `Zhipu` / `ZhipuV4` native channels in the inspected DB state
- the current Ali-backed production model set includes:
  - `qwen3.7-plus`
  - `qwen3.7-plus-2026-05-26`
  - `qwen3.7-max`
  - `qwen3.7-max-2026-06-08`
  - `deepseek-v4-pro`
  - `deepseek-v4-flash`
  - `glm-5`
  - `glm-5.1`
  - `glm-5.2`

### Current validated protocol reality

This is the most important current behavior to remember:

- The Codex `/v1/responses` path is **not** a universal path for every model exposed by sanmao.
- On the current production setup, `/v1/responses` works for the Codex/OpenAI-compatible models such as:
  - `gpt-5.4`
  - `gpt-5.5`
  - `gpt-5.4-mini`
  - `gpt-5.3-codex-spark`
  - `codex-auto-review`
- On the same setup, `/v1/responses` fails for the Ali-backed Qwen / DeepSeek / GLM models with backend relay errors.
- The Claude-style `/v1/messages` path is much broader on the current deployment and was verified to work for:
  - Claude models
  - `qwen3.7-max`
  - `qwen3.7-plus`
  - `deepseek-v4-pro`
  - `deepseek-v4-flash`
  - `glm-5`
  - `glm-5.1`
  - `glm-5.2`

### Important operational implication

For this repo, **local code changes are not enough** for production support changes.

After code lands, the remote server may still require:

- updated deployed binary/source
- service restart
- updated `options` rows in `one-api.db` such as `ModelRatio` / `CompletionRatio` / `CacheRatio`
- channel `models` updates or upstream model sync
- new channel creation for newly supported providers (for example `ZhipuV4`)

## Recommended workflow for this repo

### Phase A — local first

Always do these first locally:

1. finish code changes in the repo
2. add/update tests
3. format changes
4. run the relevant test suite if toolchain/network permits
5. review diff carefully
6. commit to git only after local work is coherent

### Phase B — deployment planning

Before touching the remote server, map the local change into remote follow-up:

- **code-only change?**
  - deploy binary/source + restart service
- **new model IDs added?**
  - also inspect/update `ModelRatio`, `CompletionRatio`, `CacheRatio`
- **new provider enabled?**
  - also create/update channels in DB/admin UI
- **admin fetch/upstream sync behavior changed?**
  - verify remote fetch path behavior against real provider credentials

### Phase C — remote verification

Preferred verification checklist:

1. `systemctl status sanmao-api.service`
2. confirm working tree / deployed revision under `/opt/sanmao/sanmao-api`
3. inspect `one-api.db` for relevant `options` and `channels`
4. verify model fetch/sync behavior
5. verify user-visible model exposure if applicable
6. restart service only after config/code are ready together

## SQL / DB inspection guidance

When inspecting remote support state, the following are high-value targets in `one-api.db`:

### options table

Check keys such as:

- `ModelRatio`
- `CompletionRatio`
- `CacheRatio`

Reason:
- existing DB overrides can shadow new code defaults
- missing model keys here can still block/cripple the newly added support

### channels table

Inspect columns such as:

- `id`
- `name`
- `type`
- `base_url`
- `models`
- `model_mapping`
- `status`
- `header_override`
- `settings`

Reason:
- a provider may be supported in code but still absent in production due to channel config

## Safe assumptions and non-assumptions

### Safe assumptions

- `sanmao-api.service` is the Go gateway service we care about
- `/opt/sanmao/sanmao-api` is the main deployment directory on `120.24.144.153`
- the deployment contains both source and DB state

### Do not assume without re-checking

- that remote DB ratios match current code defaults
- that a new provider is enabled just because code supports it
- that `/v1/models` exposure implies channels are actually configured
- that the remote git checkout matches local HEAD

## Common tasks this skill should drive

### Task: check whether a new model family is really supported remotely

Do this in order:

1. inspect remote `channels` rows for relevant provider/model IDs
2. inspect `options` ratio maps for the same IDs
3. inspect deployed code/revision if behavior depends on new routing logic
4. report separately:
   - code support
   - DB/config support
   - effective production support

### Task: prepare production rollout after a local model-support patch

Do this in order:

1. summarize local files changed
2. list required remote DB/config changes
3. identify whether a new channel type must be added
4. define restart/verification sequence
5. only then perform remote operations

## Documentation and memory rule

Whenever this skill uncovers a new stable deployment fact, capture it in one of:

- this skill itself, if it is a reusable operational rule or topology fact
- project memory, if it is a durable repo-specific fact worth surfacing in future sessions
- repo docs, if the user wants the deployment knowledge versioned with the project

Do not leave important deployment knowledge only in chat history.

## Current next-step guidance for this repo

For the current Qwen / GLM / DeepSeek support work, after local code is finalized and committed, the expected remote follow-up is:

1. deploy the updated code/binary to `/opt/sanmao/sanmao-api`
2. check whether remote `options.ModelRatio`, `CompletionRatio`, and `CacheRatio` still override the new defaults
3. update the Ali channel `models` list to include any newly exposed Qwen / DeepSeek IDs
4. add a `ZhipuV4` channel if GLM support is intended to become active remotely
5. restart `sanmao-api.service`
6. verify the server returns the new models and routes them correctly
