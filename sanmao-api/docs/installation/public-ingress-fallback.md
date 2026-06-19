# Public Ingress Fallback Notes

Last updated: 2026-06-04

## Current state

Live public ingress is:

- primary hostname: `www.sanmao.fun`
- secondary hostname on same cert: `sanmao.fun`
- TLS termination: `aa_nginx`
- config path: `/etc/aa_nginx/aa_nginx.conf`
- upstream app: `http://127.0.0.1:3000`

Current certificate SAN coverage:

- `sanmao.fun`
- `www.sanmao.fun`

## Important constraint

Do not assume a new fallback hostname can be enabled instantly.

Before introducing a real public fallback entrypoint, you need both:

1. DNS for the new hostname
2. certificate coverage for the new hostname

Without both, nginx can only safely serve the two current names.

## Recommended fallback strategy

For future public users, prefer this order:

1. Keep `www.sanmao.fun` as the canonical hostname
2. Add a second real fallback hostname, for example another subdomain
3. Issue a certificate covering both the primary and fallback names
4. Point both hostnames at the same `aa_nginx` reverse proxy
5. Keep the backend origin unchanged at `127.0.0.1:3000`

## What is already useful today

Even before a second hostname exists, you can still reduce user pain by:

- documenting `sanmao.fun` and `www.sanmao.fun` explicitly
- preferring `www.sanmao.fun` in client examples
- keeping the local SSH tunnel fallback documented for users with broken local TLS paths
- using a PID-managed local tunnel script so `127.0.0.1:13000` can be restarted safely without stale SSH control sockets

## Related files

- `docs/installation/server-state-2026-05-18.md`
- `docs/installation/local-claude-codex.md`
- `scripts/start-local-tunnel.sh`
