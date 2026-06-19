# Server State Runbook: sanmao-api

Last updated: 2026-05-18

This document records the current non-secret operational state of the live `sanmao-api` deployment so a new machine can be provisioned without rediscovering machine paths, service shape, and database tuning by trial and error.

Sensitive values such as API keys and tokens are intentionally omitted.

Related docs:

- `docs/installation/migration-checklist.md`
- `docs/installation/cold-start-deployment.md`
- `docs/installation/database-verification.md`
- `docs/channel/claude-channel-routing.md`
- `scripts/export-server-state.sh`

## Live host

- Hostname: `iZwz9da3qeqklt25cv5wwpZ`
- OS: Alibaba Cloud Linux 3 / kernel `5.10.134-18.al8.x86_64`
- Public service URL: `https://www.sanmao.fun`
- Local health endpoint: `http://127.0.0.1:3000/api/status`

## App layout on the live machine

- App root: `/opt/sanmao/sanmao-api`
- Binary: `/opt/sanmao/sanmao-api/new-api`
- Working directory: `/opt/sanmao/sanmao-api`
- Logs directory: `/opt/sanmao/sanmao-api/logs`
- SQLite database: `/opt/sanmao/sanmao-api/one-api.db`

## systemd service

The live service unit is `sanmao-api.service`.

Current effective shape:

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

## Live public ingress

The live machine is not using stock `/etc/nginx/nginx.conf`.

Public HTTPS is currently served by `aa_nginx` with:

- binary: `/usr/sbin/aa_nginx`
- master command: `aa_nginx -c /etc/aa_nginx/aa_nginx.conf`
- config file: `/etc/aa_nginx/aa_nginx.conf`

Current shape:

```nginx
server {
    listen 80;
    server_name sanmao.fun www.sanmao.fun;
    return 301 https://www.sanmao.fun$request_uri;
}

server {
    listen 443 ssl;
    server_name sanmao.fun www.sanmao.fun;

    ssl_certificate /etc/aa_nginx/ssl/sanmao/sanmao.fun.pem;
    ssl_certificate_key /etc/aa_nginx/ssl/sanmao/sanmao.fun.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    location /meeting/api/ {
        proxy_pass http://127.0.0.1:8000/api/;
    }

    location /meeting/ {
        alias /var/www/sanmao/;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
    }
}
```

Certificate SAN coverage as of 2026-06-04:

- `sanmao.fun`
- `www.sanmao.fun`

Operational consequence:

- a brand-new fallback hostname cannot be enabled safely until DNS and certificate
  coverage are prepared for that hostname
- if you want a true public fallback entrypoint, add a second hostname first and
  issue a matching certificate before changing nginx routing

## Important operational constraint

Do not inject `HTTP_PROXY`, `HTTPS_PROXY`, or `ALL_PROXY` into the service unless a real local proxy process is intentionally managed on the target machine.

On 2026-05-18 the live outage was caused by these service-level environment variables:

```ini
Environment=HTTP_PROXY=http://127.0.0.1:17890
Environment=HTTPS_PROXY=http://127.0.0.1:17890
Environment=ALL_PROXY=socks5://127.0.0.1:17890
Environment=http_proxy=http://127.0.0.1:17890
Environment=https_proxy=http://127.0.0.1:17890
Environment=all_proxy=socks5://127.0.0.1:17890
```

The process inherited those variables, but nothing was listening on `127.0.0.1:17890`, so every upstream Claude request failed during proxy connect.

Observed failure pattern:

```text
upstream error: do request failed
proxyconnect tcp: dial tcp 127.0.0.1:17890: connect: connection refused
```

If this exact symptom reappears, check `systemctl cat sanmao-api` first.

## Live Claude channel state

As of 2026-05-18 after the proxy-environment fix and Claude priority adjustment, the active Anthropic channels in the live SQLite database are:

| id | name | type | base_url | status | priority | weight | group |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | `vision-claude` | `14` | `https://coder.api.visioncoder.cn` | `1` | `20` | `0` | `default` |
| 2 | `yxai-claude` | `14` | `https://yxai.anthropic.edu.pl` | `1` | `10` | `100` | `default` |

Supported Claude models on both channels:

- `claude-sonnet-4-6`
- `claude-opus-4-6`
- `claude-sonnet-4-5-20250929`
- `claude-opus-4-5-20251101`
- `claude-haiku-4-5-20251001`

## How channel selection currently works in code

The selector is not round-robin.

Selection logic:

1. Pick the highest available `priority`.
2. Within the same priority, choose by weighted random using `weight + 10`.

Relevant code:

- `model/ability.go`
- `model/channel_cache.go`

Implication for the live state above:

- `yxai-claude` effective weight: `110`
- `vision-claude` effective weight: `10`

So the current configuration strongly prefers `yxai-claude`. It does not alternate evenly.

## Claude routing policy currently applied

The live machine is now configured to:

| channel | priority | weight | role |
| --- | --- | --- | --- |
| `vision-claude` | `20` | `0` | primary |
| `yxai-claude` | `10` | `100` | fallback |

Reason:

- `priority` expresses primary-vs-fallback.
- `weight` only biases selection within the same priority tier.

This means new channel selection should prefer `vision-claude` first and only fall through to `yxai-claude` when the higher-priority tier is unavailable.

## Other upstream channel notes

As of 2026-05-18:

- `andya-gemini` (`channel #4`, type `24`) has been disabled on the live machine
- its `channels.status` is `2`
- all of its `abilities.enabled` entries are `0`
- active default routing focus is now:
  - `vision-codex`
  - `vision-claude`
  - `yxai-claude`

## Vision Codex support policy

The live `vision-codex` channel must only expose models that the upstream
`https://coder.api.visioncoder.cn/v1/models` endpoint currently returns for the
configured key.

As of 2026-06-04, the intended `vision-codex` support set is:

- `gpt-5.4`
- `gpt-5.5`
- `gpt-5.4-mini`
- `gpt-5.3-codex-spark`
- `codex-auto-review`

Models that were previously exposed but must stay removed because the upstream
key does not actually support them:

- `gpt-5-codex`
- `gpt-5.1-codex`
- `gpt-5.1-codex-mini`

The support surface must stay aligned in three places:

1. `channels.models`
2. `abilities`
3. pricing options in `options.ModelRatio` and `options.CompletionRatio`

If you rebuild the machine or restore a database snapshot, rerun:

```bash
bash scripts/sync-vision-codex-state.sh
systemctl restart sanmao-api
```

Reason:

- current operational focus is Codex/OpenAI plus Claude primary/fallback routing
- removing Gemini from active routing simplifies debugging and cost control

## Claude CLI affinity note

The repo defaults include a channel-affinity rule named `claude cli trace`.

Properties:

- path match: `/v1/messages`
- model match: `^claude-.*$`
- affinity key source: `metadata.user_id`
- default `skip_retry_on_failure: true`

Operational consequence:

- The same Claude CLI user can stick to the same channel for the affinity TTL window.
- If that channel is unhealthy, requests can keep returning to it until cache expiry or cache clearing.

When changing Claude primary/fallback routing, also review whether channel-affinity cache should be cleared.

## Claude transport-failure cache invalidation

The codebase now includes a safeguard for sticky Claude CLI affinity:

- when a request fails with `do_request_failed`
- and that request had an active channel-affinity cache key
- the affinity cache entry is cleared

Purpose:

- prevent repeated pinning to a broken upstream channel after transport-layer failure
- allow the next request to reselect a healthy primary/fallback channel

This is especially important for Claude CLI because affinity is keyed by `metadata.user_id`.

## Minimum post-deploy checks on a new machine

Run these after provisioning:

```bash
systemctl cat sanmao-api
systemctl status sanmao-api --no-pager -l
curl -sS http://127.0.0.1:3000/api/status
sqlite3 /opt/sanmao/sanmao-api/one-api.db "select id,name,type,base_url,status,priority,weight,[group] from channels where type=14 and status=1;"
```

Check for:

- no accidental proxy environment in the service
- app healthy on port `3000`
- expected SQLite path
- expected Claude channel priority/weight state

## If you are rebuilding on another machine

Carry over at least these non-secret decisions:

- service name: `sanmao-api.service`
- app root: `/opt/sanmao/sanmao-api`
- log dir: `/opt/sanmao/sanmao-api/logs`
- SQLite path: `/opt/sanmao/sanmao-api/one-api.db`
- `GIN_MODE=release`
- no service-level proxy env by default
- explicit Claude channel priority policy
