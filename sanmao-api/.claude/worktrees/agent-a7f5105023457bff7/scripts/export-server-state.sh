#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-}"
APP_DIR="${2:-/opt/sanmao/sanmao-api}"
SERVICE_NAME="${3:-sanmao-api}"

if [[ -z "$HOST" ]]; then
  echo "usage: $0 <ssh-host> [app_dir] [service_name]" >&2
  exit 1
fi

TS="$(date +%Y-%m-%d)"
OUT="docs/installation/server-state-export-${TS}.md"

mkdir -p "$(dirname "$OUT")"

remote() {
  ssh "$HOST" "$@"
}

{
  echo "# Server State Export"
  echo
  echo "Generated at: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo
  echo "Host: \`$HOST\`"
  echo "App dir: \`$APP_DIR\`"
  echo "Service: \`$SERVICE_NAME\`"
  echo
  echo "> Secrets are intentionally omitted."
  echo
  echo "## Host"
  echo
  echo '```text'
  remote "hostnamectl --static; uname -a"
  echo '```'
  echo
  echo "## Service Unit"
  echo
  echo '```ini'
  remote "systemctl cat $SERVICE_NAME"
  echo '```'
  echo
  echo "## Service Status"
  echo
  echo '```text'
  remote "systemctl status $SERVICE_NAME --no-pager -l | sed -n '1,40p'"
  echo '```'
  echo
  echo "## App Layout"
  echo
  echo '```text'
  remote "ls -lah $APP_DIR | sed -n '1,80p'"
  echo '```'
  echo
  echo "## Health"
  echo
  echo '```json'
  remote "curl -sS http://127.0.0.1:3000/api/status"
  echo
  echo '```'
  echo
  echo "## Claude Channels"
  echo
  echo '```text'
  remote "cd $APP_DIR && sqlite3 -header -separator ' | ' one-api.db \"select id,name,type,base_url,status,priority,weight,[group],models from channels where type=14 and status=1 order by priority desc, weight desc, id asc;\""
  echo '```'
  echo
  echo "## Claude Abilities"
  echo
  echo '```text'
  remote "cd $APP_DIR && sqlite3 -header -separator ' | ' one-api.db \"select channel_id,model,enabled,priority,weight from abilities where channel_id in (select id from channels where type=14 and status=1) and model like 'claude-%' order by model, priority desc, weight desc, channel_id;\""
  echo '```'
  echo
  echo "## Key Options Snapshot"
  echo
  echo '```text'
  remote "cd $APP_DIR && sqlite3 -header -separator ' | ' one-api.db \"select key,value from options where key in ('channel_affinity_setting','RetryTimes') order by key;\""
  echo '```'
  echo
  echo "## DB Verification Queries"
  echo
  cat <<'EOF'
```sql
select id,name,type,base_url,status,priority,weight,[group],models
from channels
where type=14 and status=1
order by priority desc, weight desc, id asc;

select channel_id,model,enabled,priority,weight
from abilities
where channel_id in (
  select id from channels where type=14 and status=1
)
and model like 'claude-%'
order by model, priority desc, weight desc, channel_id;
```
EOF
} > "$OUT"

echo "wrote $OUT"
