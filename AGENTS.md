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
   `username`, and `role=personal|work|combined`. Use `has-personal` /
   `has-work` for role gates; `combined` (one Mac account holding both) makes
   both true, so never treat them as mutually exclusive — gate the work-only
   case as `has-work` and not `has-personal`. Native Macs are primary development environments; VM conditions
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

Auto-update follows `origin/main` only and skips a clone on any other branch.
Before fast-forwarding it verifies the signature on every incoming commit, then
renders the new tip from a `git archive` copy (externals and encrypted files
excluded) and runs `zsh -n` on the rendered shell files; any failure refuses the
update with a `fail` record, leaving the clone and `$HOME` untouched. There is
no canary branch: this pre-apply check is the accepted gate. nvim-config pulls
are not signature-verified (both decided 2026-10-25).
`tests/autoupdate.py` covers these gates against scratch repositories.

The auto-update timer records what happened to `chezmoi-health` — an append-only
NDJSON log at `${XDG_STATE_HOME:-~/.local/state}/chezmoi/health.ndjson`, capped at
500 lines. Read it when a box looks stale, a run-script's effect is missing (an
MCP server absent, a tool not installed), or the user reports the update "not
working":

- `chezmoi-health` — last 25 events, newest last (`ts status src item detail`).
- `chezmoi-health check` — what `zshrc` runs each shell; one stderr line + exit 1
  while anything is open: the last sync run was not `ok`, or the latest event
  for a script and item is `fail`, `timeout` or `degraded` (manual applies
  count too). A later `ok` for the same script and item closes it.
- `chezmoi-health problems` — what is open. Dismiss one by hand with
  `chezmoi-health note <src> <item> ok "resolved by hand"`.

Statuses: `ok` (converged) · `degraded` (fast-forward fine, something after it
isn't — e.g. `chezmoi init` needed) · `fail` (a run-script errored) · `timeout`
(`chezmoi apply` was killed at 720s — a run-script is hanging; the tail of
`~/.cache/chezmoi-autoupdate.last` shows where) · `skip` (an optional step was
consciously not done, e.g. a 1Password item missing).

A run script that skips because its tool is missing still exits 0, so chezmoi
records it as done. Each such script renders a `tools present at render` line
(`.chezmoitemplates/tools-present`); when the tool later appears the line
changes and the script reruns. The launchd agent and systemd service set `PATH`
to include mise shims, `~/.local/bin` and Homebrew, and the scripts prepend the
same directories, so a bare-shell apply finds what the fingerprint saw.

Two independent surfaces: `~/.cache/chezmoi-stale` (one-line human nag, only when
a fast-forward was refused) and this log (every run's outcome). A green marker
does not imply a green log.

Registration health is not runtime health. `chezmoi-health` records that a
tool or MCP server was installed or registered; `ai-tools-doctor` (read-only)
checks the installed owner, configuration, skills and, with `--probe --server
<name>`, whether a server connects and passes a reviewed smoke call. Run
`ai-tools-doctor setup` once for the locked SDK runtime; reports land in
`${XDG_STATE_HOME:-~/.local/state}/ai-tools-doctor/`. Findings live in
`docs/plans/ai-tooling-followups.md`.

## Unused configuration

`chezmoi-usage --unused` (read-only) lists declared Brewfile entries, mise
tools, aliases, `~/.local/bin` scripts, skills, MCP servers and SSH hosts with
no use in the last 90 days (`--days N`). Evidence is this machine's zsh
history, the shell commands, skill and MCP calls in Claude Code and Codex logs,
and Spotlight's last-used date for cask apps. Claude Code keeps only about 30
days of transcripts, and every source is per machine, so check each machine
before removing a fleet-wide entry. Use the logs cannot see (hooks, language
servers, libraries, login items) goes in `.usage-keep` with a reason; the
report warns about rules for things no longer declared. `tests/usage.py`
covers it against a scratch home.

## Account-local authentication

Role gates choose consumers, not vault permissions. Native accounts ignore the
legacy age-encrypted service-token and SSH-host files. Keep their source intact;
provision new authentication in the intended account, with access to only that
role's vaults. Never copy an age key, broad service-account environment, token
cache, AI login/session, scheduled task, SSH key or approval database across users.

Personal consumers use personal GitHub and Gmail/Calendar. Work consumers use
GitHub Enterprise and company services; `secret_integrations=false` prevents
shell token consumers at first bootstrap. Enable it only after account-local
work-vault authentication and reference review. GitHub and GitHub Enterprise are
reached through the `gh` CLI, not an MCP server; databases through `psql`.
Public GitHub for work is separately authenticated.

Generic context7/citra/codebase-memory registrations are the only MCP servers
shdots declares, and they are portable. ClearMoney QA skills stay personal. Generated
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
  baseline twice.
- **Codebase Memory** is installed with `--skip-config` (script 40), so it
  never writes instruction files; scripts 40/41/43 register its MCP server.
- **Portable skills:** `dot_agents/skills/<name>` → `~/.agents/skills`, read
  natively by Codex and OpenCode. Provenance and the upgrade flow are in
  `docs/ai/skills.md`. Never make `dot_agents/skills` `exact_`: installers
  (`npx skills`, herdr, browser-harness) also write there. Caveman is retired;
  script 44 prunes what its old installer left behind.
- **Claude adapter:** `dot_claude/skills/symlink_<name>` → `../../.agents/skills/<name>`.
  Claude-only skills (`eod`, `qa-manual`) stay under `dot_claude/skills`.
- **Project skills win.** Claude and OpenCode both let a global skill beat a
  same-named project skill, so never deploy a global skill (or adapter) whose
  name a project under `~/Code` already uses. See `docs/ai/skills.md`.
- **Ownership (Mac):** Codex = Homebrew cask, Claude = native installer,
  OpenCode = mise. VMs: all three via mise.
- **Deferred parity work:** `docs/plans/ai-tooling-followups.md`.
