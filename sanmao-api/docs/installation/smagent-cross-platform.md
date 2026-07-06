# smagent Cross-Platform Install

Last updated: 2026-06-19

This note defines the intended install story for the `smagent` launcher family (with `smagent` compatibility aliases) across macOS, Linux, and Windows.

## Goal

Users should be able to:

1. install a small launcher without modifying Claude Code itself
2. save one sanmao token locally
3. see the currently visible sanmao-backed gateway model list
4. pick a model and launch the local agent client with that model
5. reuse the same mental model across machines

## Current stable path

### macOS / Linux

Current supported flow:

```bash
bash scripts/install-smagent.sh
smagent-setup
smagent-models
smagent
```

This installs user-level launchers under a writable user bin directory and user-level config/tunnel helpers under `~/.config/smagent/`.

Primary commands:

- `smagent`
- `smagent-models`
- `smagent-pick`
- `smagent-setup`

Compatibility aliases remain installed:

- `smagent`
- `smagent-models`
- `smagent-pick`
- `smagent-setup`

The launcher avoids depending on the repository's `~/Desktop/.../scripts/*.sh` path at runtime, because that path can hit macOS `Operation not permitted` restrictions.

### Windows

Windows support is not fully productized yet.

The intended target is:

1. `install-smagent.ps1`
2. user-level launcher placed somewhere in the user's PATH
3. user-level config written under the user's profile directory
4. short commands matching the macOS/Linux mental model:
   - `smagent`
   - `smagent-models`
   - `smagent-pick`
   - `smagent-setup`
5. keep `smagent*` as compatibility aliases

## UX rules

The launcher family should preserve these behaviors on every platform:

- do not modify Claude Code source code
- do not depend on Claude Code's built-in `/model` picker for sanmao-backed model discovery
- always prefer a user-level launcher over executing repo-path helper scripts directly
- support a stable token/config file independent of the caller's shell environment
- support an explicit model list command and an interactive pick flow
- keep direct-launch and picker-launch both available

## Current model/product assumptions

- Codex should only expose responses-compatible models.
- The generic gateway launcher should only expose models that are actually verified for the target client path (for example, Claude Code via `/v1/messages`).
- A model showing up in `/v1/models` alone is not enough to keep it exposed.

## Next productization step

To fully claim Windows + macOS + Linux support, add:

- `scripts/install-smagent.ps1`
- compatibility guidance explaining that `smagent` is the primary UX and `smagent` remains an alias
- Windows tunnel helper equivalents
- Windows docs section in `docs/installation/local-claude-codex.md`
- a short verification checklist for each OS
