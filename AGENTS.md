# Dotfiles maintenance instructions

This repository (`~/.local/share/chezmoi`) is the chezmoi source for the home
directory and the source of truth; files such as `~/.zshrc` are rendered
outputs. This file and `CLAUDE.md` are repository-only (`.chezmoiignore.tmpl`):
they apply to agents working in this repository, never to other projects. Run
dotfiles work from here, not from a bare `~`.

> **A push to `main` can auto-deploy within 6 hours.** Legacy update timers
> pull and apply `origin/main`; publishing a migration branch does not deploy it.
> Native account onboarding defaults to manual updates. Review rollout before
> changing `main`.

> **Fleet plan in progress:** `docs/plans/account-aware-macos.md` holds the target
> topology, the decision log, the gotchas, and the remaining phases. Read it
> before changing provisioning, SSH keys, secrets, or machine roles.

## Required workflow

1. Before changing managed configuration, inspect both layers:
   - `chezmoi git status --short --branch`
   - `chezmoi status`
   - `chezmoi diff`
2. Prefer `chezmoi edit <target>` or edit the matching file under
   `~/.local/share/chezmoi`. Do not directly edit a rendered target as the
   primary workflow.
3. Keep machine and account identity separate: `kind=mac|vm`, `hostname`,
   `username`, and `role=personal|work`. Use `has-personal` / `has-work` for
   role gates. Native Macs are primary development environments; VM conditions
   describe optional Linux compatibility only. Before changing account roles,
   secrets, onboarding or scheduling, read `docs/plans/account-aware-macos.md`.
4. If a rendered target was changed outside chezmoi, inspect it with
   `chezmoi diff` and reconcile it with `chezmoi merge <target>`. Use
   `chezmoi re-add` only for non-template files.
5. Before applying, render or syntax-check the affected configuration and run
   `chezmoi apply --dry-run --verbose`. Then apply with `chezmoi apply` and
   smoke-test the affected program.
6. After applying, require `chezmoi status` to be clean. Review the source
   diff with `chezmoi git diff`.

## Externals (not chezmoi source)

Some targets are pulled straight from git by `.chezmoiexternal.toml`, not
rendered from this repo. Do **not** `chezmoi edit`, `chezmoi add`, or `chezmoi
re-add` them, and do not expect them under `~/.local/share/chezmoi`:

- **`~/.config/nvim`** — the Neovim config lives in its own repo,
  [`shahwan42/nvim-config`](https://github.com/shahwan42/nvim-config)
  (`type = "git-repo"`, `refreshPeriod = 0`). To change it, edit the files in
  place, then `git -C ~/.config/nvim commit` and `git push` to that repo. Every
  `chezmoi apply` / `chezmoi update` runs `git pull` in it. `chezmoi-autoupdate`
  also pulls it (`--ff-only`) on runs where this repo has nothing new, logging
  `autoupdate nvim-config` to `chezmoi-health`. Its local `origin`
  is SSH (for pushing); the external URL is HTTPS (so fresh machines clone
  without a key) — a new machine that needs to push runs
  `git -C ~/.config/nvim remote set-url origin git@github.com:shahwan42/nvim-config.git`.
- **`~/.local/share/zsh/plugins/*`** — upstream zsh plugins, refreshed at most
  every 168h.

For Zsh changes, render and validate before applying:

```sh
chezmoi cat ~/.zshrc | zsh -n
chezmoi apply --dry-run --verbose
```

After applying, start a fresh interactive shell and check for startup errors:

```sh
zsh -i -c exit
```

## Packages, Git, and secrets

- Declare macOS command-line dependencies in the tracked `Brewfile`; do not
  vendor package-manager payloads or plugin checkouts into this repository.
- Preserve unrelated changes in both the source repository and rendered home
  directory.
- Never add credentials, tokens, private keys, machine-generated SSH state,
  or unencrypted secrets. The tracked pre-commit hook must continue to run
  gitleaks.
- Commit and push only when the user explicitly requests it. Otherwise report
  the reviewed diff and the exact `chezmoi git add`, `commit`, and `push`
  commands needed to publish it.
- On another machine, check `chezmoi git status` and `chezmoi status`, then use
  `chezmoi update` to pull and apply published changes.

## mise toolchain

`~/.config/mise/config.toml` is fully chezmoi-managed and provides one fleet
toolchain. Exact versions are pinned in the source template; `lockfile = false`
is intentional because a shared lockfile accumulates platform-specific entries
and creates cross-platform drift. Never edit the rendered config by hand as the
primary workflow. Edit `dot_config/mise/config.toml.tmpl`, then run
`chezmoi apply`. A `M .config/mise/config.toml` in `chezmoi status` (also
surfaced by the shell marker and `chezmoi-health`) means mise changed the
rendered file out of band; either promote the intended version changes into the
template or restore the rendered file with `chezmoi apply --force`.

**Add a tool to the fleet** — the only supported way:

1. Edit `dot_config/mise/config.toml.tmpl`; put it in the shared block unless it
   is genuinely role-specific (there is a `# --- work only ---` block).
2. Render and review with `chezmoi cat ~/.config/mise/config.toml` and
   `chezmoi diff ~/.config/mise/config.toml`.
3. `chezmoi apply` — `run_onchange_after_20-mise-install` runs `mise install`.
4. Smoke-test the affected tool, require `chezmoi status` to be clean, and
   commit the template change. There is no global `mise.lock` to re-add.

**Promote an intentional global upgrade:** if `mise up` or another mise command
updates the rendered config, copy only the intended version changes into
`dot_config/mise/config.toml.tmpl`, preserving its role/kind conditions. Render,
review, and apply as above; do not use `chezmoi re-add` on this template.

**Experiment without touching the fleet:**

- One-off: `mise exec <tool>@<ver> -- <cmd>` — writes nothing.
- Longer: a project-local `mise.toml` in the working directory — any adjacent
  lockfile is project-local and has zero global impact.
- Do **not** use `mise use -g` or `~/.config/mise/conf.d/`; they change the
  global toolchain outside the managed template and show up as drift. If the
  experiment graduates, promote it with the workflow above.

## Linux compatibility

`as-host/fdx-dev` is the temporary canonical compatibility VM. The stopped
`fdx-host/fdx-dev` is legacy preserved state. Leave VM lifecycle and Tailscale
identity unchanged unless explicitly requested. `provision/` retains the old
VM-first tooling; it is not used for native account onboarding.

## Fleet health

The auto-update timer records what happened to `chezmoi-health` — an append-only
NDJSON log at `${XDG_STATE_HOME:-~/.local/state}/chezmoi/health.ndjson`, capped at
500 lines. Read it when a box looks stale, a run-script's effect is missing (an
MCP server absent, a tool not installed), or the user reports the update "not
working":

- `chezmoi-health` — last 25 events, newest last (`ts status src item detail`).
- `chezmoi-health check` — what `zshrc` runs each shell; one stderr line + exit 1
  when the last sync run was not `ok`.

Statuses: `ok` (converged) · `degraded` (fast-forward fine, something after it
isn't — e.g. `chezmoi init` needed) · `fail` (a run-script errored) · `timeout`
(`chezmoi apply` was killed at 900s — a run-script is hanging; the tail of
`~/.cache/chezmoi-autoupdate.last` shows where) · `skip` (an optional step was
consciously not done, e.g. a 1Password item missing).

Two independent surfaces: `~/.cache/chezmoi-stale` (one-line human nag, only when
a fast-forward was refused) and this log (every run's outcome). A green marker
does not imply a green log.

## Account-local authentication

Role gates choose consumers, not vault permissions. Native accounts ignore the
legacy age-encrypted service-token and SSH-host files. Keep their source intact;
provision new authentication in the intended account, with access to only that
role's vaults. Never copy an age key, broad service-account environment, token
cache, AI login/session, scheduled task, SSH key or approval database across users.

Personal consumers use personal GitHub and Gmail/Calendar. Work consumers use
GitHub Enterprise and company services; `secret_integrations=false` prevents
automatic PAT acquisition at first bootstrap. Enable it only after account-local
work-vault authentication and reference review. `mcp-github-register` registers
only the active role's server. Public GitHub for work is separately authenticated.

Generic context7/citra/codebase-memory registrations are portable. Personal
project database declarations and ClearMoney QA skills stay personal. Generated
client configuration and trust records remain local; the source never copies them.

## AI tooling layout

Global agent instructions and portable skills are owned here; project repos own
their own `AGENTS.md`, `.agents/skills`, and MCP config.

- **Shared instruction baseline:** `.chezmoitemplates/ai-baseline.md` (output
  preferences, mermaid rule, codebase-memory graph guidance). Rendered into
  each tool's native global file: `dot_codex/AGENTS.md.tmpl`,
  `dot_claude/CLAUDE.md.tmpl` (plus Claude-only lines), and
  `dot_config/opencode/instructions/baseline.md.tmpl` (referenced from
  `opencode.jsonc` `instructions` by script 41). Edit the baseline once.
  `~/.config/opencode/AGENTS.md` is create-only (`create_AGENTS.md`): it must
  exist, or OpenCode falls back to `~/.claude/CLAUDE.md` and loads the
  baseline twice; Caveman appends its fenced block to it.
- **Codebase Memory** is installed with `--skip-config` (script 40), so it
  never writes instruction files; scripts 40/41/43 register its MCP server.
- **Portable skills:** `dot_agents/skills/<name>` → `~/.agents/skills`, read
  natively by Codex and OpenCode. Provenance and the upgrade flow are in
  `docs/ai/skills.md`. Never make `dot_agents/skills` `exact_`: installers
  (Caveman, `npx skills`, herdr, browser-harness) also write there.
- **Claude adapter:** `dot_claude/skills/symlink_<name>` → `../../.agents/skills/<name>`.
  Claude-only skills (`eod`, `qa-manual`) stay under `dot_claude/skills`.
- **Project skills win.** Claude and OpenCode both let a global skill beat a
  same-named project skill, so never deploy a global skill (or adapter) whose
  name a project under `~/Code` already uses. See `docs/ai/skills.md`.
- **Ownership (Mac):** Codex = Homebrew cask, Claude = native installer,
  OpenCode = mise. VMs: all three via mise.
- **Deferred parity work:** `docs/plans/ai-tooling-followups.md`.
