# Claude Channel Routing

Last updated: 2026-05-18

This document records the current intended Claude routing policy and the database fields that control it.

Secrets are omitted.

Current scope note:

- this document describes the active Claude routing path
- the live `andya-gemini` channel is currently disabled and does not participate in active default routing

## Current live intended state

Primary channel:

- name: `vision-claude`
- base URL: `https://coder.api.visioncoder.cn`
- priority: `20`
- weight: `0`
- group: `default`

Fallback channel:

- name: `yxai-claude`
- base URL: `https://yxai.anthropic.edu.pl`
- priority: `10`
- weight: `100`
- group: `default`

Shared supported models:

- `claude-sonnet-4-6`
- `claude-opus-4-6`
- `claude-sonnet-4-5-20250929`
- `claude-opus-4-5-20251101`
- `claude-haiku-4-5-20251001`

## How routing works

Claude channel selection is not round-robin.

The selector does this:

1. choose the highest available `priority`
2. inside the same priority tier, choose by weighted random using `weight + 10`

Implications:

- if you want one channel to be primary and another to be fallback, change `priority`
- if you only change `weight`, both channels still remain in the same priority tier

## Database tables that matter

Main channel rows:

- `channels`

Per-model ability rows:

- `abilities`

When you change channel `priority` or `weight`, make sure matching `abilities` rows stay aligned.

## Queries to inspect current Claude state

```sql
select id,name,type,base_url,status,priority,weight,[group],models
from channels
where type=14 and status=1
order by priority desc, weight desc, id asc;
```

```sql
select channel_id,model,enabled,priority,weight
from abilities
where channel_id in (
  select id from channels where type=14 and status=1
)
and model like 'claude-%'
order by model, priority desc, weight desc, channel_id;
```

## Recommended update pattern

If you want to switch primary/fallback:

1. update `channels.priority`
2. update matching `abilities.priority`
3. verify both tables
4. if Claude CLI traffic behaves sticky, clear channel-affinity cache

## Affinity caveat

Claude CLI requests can be pinned by the `claude cli trace` affinity rule using `metadata.user_id`.

This means:

- even if the database priority is correct
- a user may temporarily continue hitting a previously cached channel

The code now clears affinity cache on `do_request_failed`, but manual cache clearing can still be useful after a routing policy change.
