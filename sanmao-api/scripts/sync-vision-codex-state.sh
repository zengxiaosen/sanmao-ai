#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/opt/sanmao/sanmao-api}"
DB_PATH="${APP_DIR}/one-api.db"
CHANNEL_ID="${CHANNEL_ID:-1}"
CHANNEL_NAME="${CHANNEL_NAME:-vision-codex}"
GROUP_NAME="${GROUP_NAME:-default}"

if [[ ! -f "${DB_PATH}" ]]; then
  echo "database not found: ${DB_PATH}" >&2
  exit 1
fi

MODELS="gpt-5.4,gpt-5.5,gpt-5.4-mini,gpt-5.3-codex-spark,codex-auto-review"
PRIORITY="${PRIORITY:-8}"
WEIGHT="${WEIGHT:-80}"

sqlite3 "${DB_PATH}" <<SQL
begin;

update channels
set models='${MODELS}'
where id=${CHANNEL_ID} and name='${CHANNEL_NAME}';

delete from abilities
where channel_id=${CHANNEL_ID}
  and model in ('gpt-5-codex','gpt-5.1-codex','gpt-5.1-codex-mini');

insert or replace into abilities ("group", model, channel_id, enabled, priority, weight, tag)
values
  ('${GROUP_NAME}','gpt-5.4',${CHANNEL_ID},1,${PRIORITY},${WEIGHT},null),
  ('${GROUP_NAME}','gpt-5.5',${CHANNEL_ID},1,${PRIORITY},${WEIGHT},null),
  ('${GROUP_NAME}','gpt-5.4-mini',${CHANNEL_ID},1,${PRIORITY},${WEIGHT},null),
  ('${GROUP_NAME}','gpt-5.3-codex-spark',${CHANNEL_ID},1,${PRIORITY},${WEIGHT},null),
  ('${GROUP_NAME}','codex-auto-review',${CHANNEL_ID},1,${PRIORITY},${WEIGHT},null);

update options
set value=json_set(
  value,
  '$.gpt-5.5', 7.5,
  '$.gpt-5.4-mini', 7.5,
  '$.gpt-5.3-codex-spark', 5.5,
  '$.codex-auto-review', 5.5
)
where key='ModelRatio';

update options
set value=json_set(
  value,
  '$.gpt-5.5', 8,
  '$.gpt-5.4-mini', 6,
  '$.gpt-5.3-codex-spark', 8,
  '$.codex-auto-review', 8
)
where key='CompletionRatio';

commit;
SQL

echo "synced ${CHANNEL_NAME} in ${DB_PATH}"
sqlite3 -header -separator ' | ' "${DB_PATH}" "select id,name,models from channels where id=${CHANNEL_ID};"
sqlite3 -header -separator ' | ' "${DB_PATH}" "select \"group\",model,enabled,priority,weight from abilities where channel_id=${CHANNEL_ID} order by model;"
