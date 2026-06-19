# GitHub Actions Server Deploy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trigger deployment from GitHub while keeping all build and restart work on `aliyun-120`.

**Architecture:** GitHub Actions acts as the orchestration layer only. A checked-in server deployment script executes on `aliyun-120` to pull the latest code, build frontend and backend in-place, restart `sanmao-api.service`, and validate the local health endpoint before traffic is switched in Nginx.

**Tech Stack:** GitHub Actions, SSH, Bun, Go, systemd, aaPanel Nginx

---

### Task 1: Make frontend installs reproducible

**Files:**
- Modify: `.gitignore`
- Create: `web/bun.lock`

- [ ] **Step 1: Ensure `web/bun.lock` is versioned**

Remove the ignore rule for `web/bun.lock` and stage the lockfile.

- [ ] **Step 2: Verify ignore behavior**

Run: `git status --short .gitignore web/bun.lock`
Expected: both files appear as tracked changes.

### Task 2: Add server-side deployment script

**Files:**
- Create: `scripts/deploy-on-server.sh`

- [ ] **Step 1: Write deployment script**

Script responsibilities:
- accept optional branch argument
- update repo in `/opt/sanmao/sanmao-api`
- run `bun install --frozen-lockfile`
- build frontend with `DISABLE_ESLINT_PLUGIN=true`
- build backend binary with version metadata
- restart `sanmao-api.service`
- health-check `http://127.0.0.1:3000/api/status`

- [ ] **Step 2: Check shell syntax**

Run: `bash -n scripts/deploy-on-server.sh`
Expected: exit code 0.

### Task 3: Add GitHub Actions deploy workflow

**Files:**
- Create: `.github/workflows/deploy-server.yml`

- [ ] **Step 1: Write workflow**

Trigger on:
- `push` to `main`
- `workflow_dispatch`

Steps:
- checkout
- open SSH agent with repository secret key
- add server to `known_hosts`
- run remote deploy script with branch name

- [ ] **Step 2: Validate workflow YAML**

Run: `python3 - <<'PY' ...` or another YAML parser if available.
Expected: file parses successfully.

### Task 4: Push and activate deployment path

**Files:**
- Modify: server repo checkout at `/opt/sanmao/sanmao-api`
- Modify: `/etc/aa_nginx/aa_nginx.conf`

- [ ] **Step 1: Commit and push workflow changes**

Run git add/commit/push for the new workflow, script, docs, `.gitignore`, and `web/bun.lock`.

- [ ] **Step 2: Ensure GitHub secrets exist**

Required secret names:
- `ALIYUN_HOST`
- `ALIYUN_USER`
- `ALIYUN_SSH_KEY`
- optional `ALIYUN_PORT`

- [ ] **Step 3: Run workflow**

Use GitHub Actions manual dispatch or push-triggered run and confirm the remote script succeeds.

- [ ] **Step 4: Switch Nginx upstream**

Change `location /` to proxy to `http://127.0.0.1:3000` and reload Nginx.

- [ ] **Step 5: Verify production**

Verify:
- `systemctl status sanmao-api.service`
- `curl http://127.0.0.1:3000/api/status`
- `https://www.sanmao.fun/`
- `https://www.sanmao.fun/api/status`
