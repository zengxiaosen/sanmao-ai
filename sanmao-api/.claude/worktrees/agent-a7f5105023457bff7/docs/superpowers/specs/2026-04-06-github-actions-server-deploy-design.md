# GitHub Actions Server Deploy Design

**Context**

This project should no longer rely on local machine builds or deployments. Deployment should be triggered from GitHub, but the actual build and restart should happen on the single production server `aliyun-120`.

**Recommended Approach**

Use GitHub Actions as a remote trigger only. On pushes to `main` or manual dispatch, the workflow connects to `aliyun-120` over SSH and runs a checked-in deployment script inside `/opt/sanmao/sanmao-api`.

This keeps the deployment path simple:
- GitHub remains the source of truth for code changes.
- The production server performs `git fetch/reset`, frontend build, backend build, and service restart locally.
- Nginx continues to terminate TLS and proxy traffic to the Go service on port `3000`.

**Alternatives Considered**

1. GitHub-hosted runner builds artifacts and uploads them to the server.
This adds unnecessary complexity because there is only one server and the project has already shown dependency drift issues between environments.

2. Pure server-side webhook without GitHub Actions.
This reduces GitHub observability and makes manual re-runs less convenient than `workflow_dispatch`.

**Design**

The implementation has four parts:

1. Commit `web/bun.lock` and stop ignoring it so frontend dependencies are reproducible.
2. Add a server deployment script that:
   - updates the repo to the target branch,
   - runs `bun install --frozen-lockfile`,
   - builds the frontend with the existing `VITE_REACT_APP_VERSION` convention,
   - builds the backend binary,
   - restarts `sanmao-api.service`,
   - performs a local health check.
3. Add a GitHub Actions workflow that SSHes into the server and invokes that script.
4. Switch Nginx `location /` from `127.0.0.1:8000` to `127.0.0.1:3000` after the service is healthy.

**Operational Notes**

- The workflow should use standard repository secrets for SSH connectivity.
- The server remains the only build machine.
- Existing `/meeting/` and `/meeting/api/` routes must remain unchanged.
- Project-protected `new-api` / `QuantumNous` identifiers must not be altered.
