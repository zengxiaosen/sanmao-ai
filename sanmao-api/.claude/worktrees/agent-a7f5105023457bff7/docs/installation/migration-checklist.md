# Migration Checklist: sanmao-api

Use this checklist when moving `sanmao-api` to a new machine or rebuilding the current host.

This document intentionally excludes secrets. Pair it with your secure secret store.

## 1. Directory layout

Create or confirm:

- app root: `/opt/sanmao/sanmao-api`
- logs dir: `/opt/sanmao/sanmao-api/logs`
- database path: `/opt/sanmao/sanmao-api/one-api.db`

Expected runtime shape:

- binary path: `/opt/sanmao/sanmao-api/new-api`
- working directory: `/opt/sanmao/sanmao-api`
- HTTP port: `3000`

## 2. Service unit

Install a `sanmao-api.service` unit with:

- `WorkingDirectory=/opt/sanmao/sanmao-api`
- `ExecStart=/opt/sanmao/sanmao-api/new-api --port 3000 --log-dir /opt/sanmao/sanmao-api/logs`
- `Restart=always`
- `Environment=GIN_MODE=release`

Do not inject:

- `HTTP_PROXY`
- `HTTPS_PROXY`
- `ALL_PROXY`
- lowercase proxy variants

unless you are also explicitly deploying and supervising a real local proxy process.

## 3. Database file

Restore or copy:

- `/opt/sanmao/sanmao-api/one-api.db`

After restore, verify:

```bash
sqlite3 /opt/sanmao/sanmao-api/one-api.db "select count(*) from channels;"
sqlite3 /opt/sanmao/sanmao-api/one-api.db "select count(*) from abilities;"
```

## 4. Claude channel policy

Current intended policy:

- `vision-claude` is primary
- `yxai-claude` is fallback

Verify:

```bash
sqlite3 -header -separator ' | ' /opt/sanmao/sanmao-api/one-api.db \
  "select id,name,priority,weight,[group],base_url from channels where type=14 and status=1 order by priority desc, weight desc, id asc;"
```

Expected relative ordering:

- `vision-claude` priority higher than `yxai-claude`

## 4.1 Disabled Gemini channel note

Current live expectation:

- `andya-gemini` remains disabled unless there is an explicit business need to restore Gemini traffic

Verify if needed:

```bash
sqlite3 -header -separator ' | ' /opt/sanmao/sanmao-api/one-api.db \
  "select id,name,type,status,priority,weight,[group] from channels where id=4;"
```

## 5. Channel affinity

Review whether the default `claude cli trace` affinity rule is acceptable for the new host.

Operational notes:

- Claude CLI affinity key is `metadata.user_id`
- affinity can pin a user to one Claude channel
- code now clears affinity cache on `do_request_failed`

If the new host is restored from an old database snapshot and traffic behaves strangely, clear affinity cache before blaming routing.

## 6. Health checks

After startup:

```bash
systemctl daemon-reload
systemctl enable sanmao-api
systemctl restart sanmao-api
systemctl status sanmao-api --no-pager -l
curl -sS http://127.0.0.1:3000/api/status
```

## 7. Upstream connectivity spot checks

Run direct connectivity checks from the host:

```bash
curl -sS -o /dev/null -w '%{http_code} %{remote_ip}\n' https://coder.api.visioncoder.cn/v1/messages?beta=true
curl -sS -o /dev/null -w '%{http_code} %{remote_ip}\n' https://yxai.anthropic.edu.pl/v1/messages?beta=true
```

You do not need a `200` here. A `404` or `405` is enough to prove basic reachability.

## 8. Failure signatures to recognize immediately

If you see:

```text
upstream error: do request failed
proxyconnect tcp: dial tcp 127.0.0.1:<port>: connect: connection refused
```

then inspect service-level proxy environment first:

```bash
systemctl cat sanmao-api
```

## 9. Recommended post-migration smoke tests

- browser/API: `GET /api/status`
- Claude-compatible request through `/v1/messages`
- confirm logs are written to `/opt/sanmao/sanmao-api/logs`
- confirm no new `do request failed` entries after smoke test

## 10. Local development note

If you are running local `go test` or `go mod download` from a workstation or sandboxed agent:

- local proxy environment can pollute Go network access
- clearing proxy env may still fail if the execution sandbox has no outbound DNS/network

Useful isolation pattern:

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
    -u http_proxy -u https_proxy -u all_proxy \
    GOCACHE=$(pwd)/.gocache-local \
    GOMODCACHE=$(pwd)/.gomodcache-local \
    GOPROXY=https://proxy.golang.org,direct \
    go test ./...
```

If this still fails with `lookup proxy.golang.org: no such host`, the blocker is the execution environment, not the application logic.
