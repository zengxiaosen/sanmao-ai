# Cold-Start Deployment Manual

This guide is for bringing up `sanmao-api` on a fresh machine with minimal rediscovery.

Use alongside:

- `docs/installation/server-state-2026-05-18.md`
- `docs/installation/migration-checklist.md`
- `docs/channel/claude-channel-routing.md`

## Goal

Recover a working server with:

- correct filesystem layout
- working systemd service
- restored SQLite database
- known Claude primary/fallback routing
- no accidental broken proxy settings

## 1. Prepare directories

```bash
mkdir -p /opt/sanmao/sanmao-api
mkdir -p /opt/sanmao/sanmao-api/logs
```

## 2. Sync repository

```bash
cd /opt/sanmao/sanmao-api
git clone <repo-url> .
git checkout <branch>
```

## 3. Restore data

Restore the SQLite database to:

```bash
/opt/sanmao/sanmao-api/one-api.db
```

Then verify it exists:

```bash
ls -lah /opt/sanmao/sanmao-api/one-api.db
sqlite3 /opt/sanmao/sanmao-api/one-api.db "select count(*) from channels;"
sqlite3 /opt/sanmao/sanmao-api/one-api.db "select count(*) from abilities;"
```

## 4. Build the application

The repo already includes a server deploy script:

```bash
scripts/deploy-on-server.sh <branch>
```

If building manually:

```bash
cd /opt/sanmao/sanmao-api/web
bun install --frozen-lockfile
NODE_OPTIONS='--max-old-space-size=8192' DISABLE_ESLINT_PLUGIN=true bun run build

cd /opt/sanmao/sanmao-api
go mod download
CGO_ENABLED=1 go build -ldflags "-s -w -X 'new-api/common.Version=$(cat VERSION)'" -o new-api
```

## 5. Install the service

Create `/etc/systemd/system/sanmao-api.service` from the repo template, then adapt:

- `WorkingDirectory=/opt/sanmao/sanmao-api`
- `ExecStart=/opt/sanmao/sanmao-api/new-api --port 3000 --log-dir /opt/sanmao/sanmao-api/logs`
- `User=root` or your chosen service user
- `Environment=GIN_MODE=release`

Important:

- do not add `HTTP_PROXY`, `HTTPS_PROXY`, or `ALL_PROXY` unless you intentionally operate a real local proxy process

## 6. Start and verify

```bash
systemctl daemon-reload
systemctl enable sanmao-api
systemctl restart sanmao-api
systemctl status sanmao-api --no-pager -l
curl -sS http://127.0.0.1:3000/api/status
```

## 7. Verify Claude routing state

```bash
sqlite3 -header -separator ' | ' /opt/sanmao/sanmao-api/one-api.db \
  "select id,name,priority,weight,[group],base_url from channels where type=14 and status=1 order by priority desc, weight desc, id asc;"
```

Desired default behavior:

- `vision-claude` higher priority
- `yxai-claude` lower priority

## 8. If you changed machine or restored an old DB snapshot

Clear assumptions that may be stale:

- systemd proxy env
- Claude channel affinity cache
- outdated channel priorities

If traffic seems pinned to an old Claude channel after restore, review channel affinity and clear the cache.

## 9. Export fresh machine state back into the repo

After the new machine is healthy, generate a redacted snapshot:

```bash
./scripts/export-server-state.sh root@your-host
```

This writes a dated markdown snapshot into `docs/installation/`.

Commit that snapshot if you want the repo to reflect current reality.

