# Database Verification Queries

Use these queries after restoring `one-api.db` onto a new machine.

Goal:

- confirm the database is present
- confirm Claude routing policy is intact
- confirm `channels` and `abilities` are aligned
- confirm `vision-codex` only exposes upstream-supported models

## 1. Basic table counts

```sql
select count(*) as channels_count from channels;
select count(*) as abilities_count from abilities;
```

## 2. Active Claude channels

```sql
select id,name,type,base_url,status,priority,weight,[group],models
from channels
where type=14 and status=1
order by priority desc, weight desc, id asc;
```

What to check:

- expected Claude channels exist
- `vision-claude` has higher priority than `yxai-claude`
- both channels are enabled

## 3. Claude abilities

```sql
select channel_id,model,enabled,priority,weight
from abilities
where channel_id in (
  select id from channels where type=14 and status=1
)
and model like 'claude-%'
order by model, priority desc, weight desc, channel_id;
```

What to check:

- every intended Claude model exists for both primary and fallback channels
- ability `priority` matches the corresponding channel `priority`
- ability `weight` matches the corresponding channel `weight`

## 4. Detect mismatched priority/weight between channels and abilities

```sql
select
  c.id as channel_id,
  c.name as channel_name,
  a.model,
  c.priority as channel_priority,
  a.priority as ability_priority,
  c.weight as channel_weight,
  a.weight as ability_weight
from channels c
join abilities a on a.channel_id = c.id
where c.type = 14
  and c.status = 1
  and a.model like 'claude-%'
  and (
    ifnull(c.priority, 0) != ifnull(a.priority, 0)
    or ifnull(c.weight, 0) != ifnull(a.weight, 0)
  )
order by c.id, a.model;
```

Expected result:

- no rows

## 5. Confirm primary/fallback ordering directly

```sql
select
  name,
  priority,
  weight,
  case
    when priority = (select max(priority) from channels where type=14 and status=1) then 'top-tier'
    else 'lower-tier'
  end as routing_tier
from channels
where type=14 and status=1
order by priority desc, weight desc, id asc;
```

## 6. Optional snapshot export command

To export a redacted live machine snapshot back into the repo:

```bash
./scripts/export-server-state.sh root@your-host
```

## 7. Vision Codex channel support

```sql
select id,name,models
from channels
where name = 'vision-codex';

select "group",model,enabled,priority,weight
from abilities
where channel_id = (
  select id from channels where name = 'vision-codex'
)
order by model;

select key,value
from options
where key in ('ModelRatio','CompletionRatio');
```

What to check:

- `channels.models` contains only:
  - `gpt-5.4`
  - `gpt-5.5`
  - `gpt-5.4-mini`
  - `gpt-5.3-codex-spark`
  - `codex-auto-review`
- `abilities` for `vision-codex` contain the same set
- old fake support entries are absent:
  - `gpt-5-codex`
  - `gpt-5.1-codex`
  - `gpt-5.1-codex-mini`
- `options.ModelRatio` and `options.CompletionRatio` include values for:
  - `gpt-5.5`
  - `gpt-5.4-mini`
  - `gpt-5.3-codex-spark`
  - `codex-auto-review`
