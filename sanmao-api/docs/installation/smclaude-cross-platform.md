# smclaude Cross-Platform Install

Last updated: 2026-06-19

This note defines the intended install story for the `smclaude` launcher family across macOS, Linux, and Windows.

## Goal

Users should be able to:

1. install a small launcher without modifying Claude Code itself
2. save one sanmao token locally
3. see the currently visible sanmao-backed model list
4. pick a model and launch Claude with that model
5. reuse the same mental model across machines

## Current stable path

### macOS / Linux

Current supported flow:

```bash
bash scripts/install-smclaude.sh
smclaude-setup
smclaude-models
smclaude
```

This installs user-level launchers under a writable user bin directory and user-level config/tunnel helpers under `~/.config/sanmao-claude/`.

Current commands:

- `smclaude`
- `smclaude-models`
- `smclaude-pick`
- `smclaude-setup`

The launcher avoids depending on the repository's `~/Desktop/.../scripts/*.sh` path at runtime, because that path can hit macOS `Operation not permitted` restrictions.

### Windows

Windows support is not fully productized yet.

The intended target is:

1. `install-smclaude.ps1`
2. user-level launcher placed somewhere in the user's PATH
3. user-level config written under the user's profile directory
4. short commands matching the macOS/Linux mental model:
   - `smclaude`
   - `smclaude-models`
   - `smclaude-pick`
   - `smclaude-setup`

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
- Claude-through-sanmao should expose only models that are actually verified through `/v1/messages` with real requests.
- A model showing up in `/v1/models` alone is not enough to keep it exposed.

## Next productization step

To fully claim Windows + macOS + Linux support, add:

- `scripts/install-smclaude.ps1`
- Windows tunnel helper equivalents
- Windows docs section in `docs/installation/local-claude-codex.md`
- a short verification checklist for each OS
