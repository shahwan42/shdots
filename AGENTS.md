# Dotfiles maintenance instructions

This home directory is managed by chezmoi. The Git repository at
`~/.local/share/chezmoi` is the source of truth; files such as `~/.zshrc` are
rendered outputs.

> **A push auto-deploys fleet-wide within 6 hours.** Every machine runs a
> chezmoi auto-update timer (launchd on Macs, systemd on VMs) that pulls and
> applies `origin/main`. Treat every push as a deployment.

## Required workflow

1. Before changing managed configuration, inspect both layers:
   - `chezmoi git status --short --branch`
   - `chezmoi status`
   - `chezmoi diff`
2. Prefer `chezmoi edit <target>` or edit the matching file under
   `~/.local/share/chezmoi`. Do not directly edit a rendered target as the
   primary workflow.
3. Preserve chezmoi templates and the existing `role` (`personal` or `work`)
   and `kind` (`mac` or `vm`) conditions. Do not replace a template with one
   machine's rendered output.
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
  `chezmoi apply` / `chezmoi update` runs `git pull` in it. Its local `origin`
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

`~/.config/mise/config.toml` and `~/.config/mise/mise.lock` are **fully
chezmoi-managed and identical on every machine** — one fleet toolchain, kept in
sync. Never edit `~/.config/mise/config.toml` by hand; edit the source
`dot_config/mise/config.toml.tmpl` and `chezmoi apply`. A `M .config/mise/…` in
`chezmoi status` (also surfaced by the shell marker and `chezmoi-health`) means a
tool was added out of band — reconcile it, don't leave it.

**Add a tool to the fleet** — the only supported way:

1. Edit `dot_config/mise/config.toml.tmpl`; put it in the shared block unless it
   is genuinely role-specific (there is a `# --- work only ---` block).
2. `chezmoi apply` — `run_onchange_after_20-mise-install` runs `mise install`,
   which also maintains `mise.lock` (`lockfile = true`; there is no `mise lock`
   subcommand in the pinned version).
3. `chezmoi re-add ~/.config/mise/mise.lock`.
4. Commit **`config.toml.tmpl` and `mise.lock` together** in one push. A tool in
   the config but missing from the lock makes every other machine's
   `mise install` rewrite the lock — perpetual `mise.lock` drift. This is the #1
   cause of that drift.
5. `mise.lock` holds per-platform checksums. The first machine of each platform
   (one Mac, one VM) to `mise install` after the push adds its platform's rows;
   `chezmoi re-add` + a follow-up commit from that machine finishes the lock,
   after which it is stable.

**Experiment without touching the fleet:**

- One-off: `mise exec <tool>@<ver> -- <cmd>` — writes nothing.
- Longer: a project-local `mise.toml` in the working directory — it gets its own
  adjacent lock, zero global impact.
- Do **not** use `mise use -g` or `~/.config/mise/conf.d/` — both feed the global
  `mise.lock` and show up as drift. If the experiment graduates, add it via the
  steps above.

## Dev VM spec

The two Multipass dev VMs — `as-dev` (personal) and `fdx-dev` (work) — share one
hardware spec. Do not re-derive it; it lives in two files, both under
`~/.local/share/chezmoi/provision` (which is chezmoi-ignored — edit them directly,
there is no rendered copy):

- **CPU / RAM / disk / image** — the `CPUS` / `MEMORY` / `DISK` / `IMAGE` constants
  at the top of `provision/launch-dev-vm.sh` (currently 6 / 12G / 220G / 24.04).
- **Swap and timezone** — `provision/dev-vm-cloud-init.yaml` (currently 6G, Africa/Cairo).

Two kinds of request:

1. **Launch or relaunch one VM at a different size** — pass `--cpus` / `--memory` /
   `--disk` as one-off flags to `launch-dev-vm.sh`. Change nothing in the repo.
2. **Make a new size the default** — change the constant, then grep the repo for
   each old value you changed and fix every comment and doc that quotes it (this
   section, both `README.md` files, the `provision/*` file headers).

Never `multipass set` a running VM unless asked. Disk can only grow, and only while
the VM is stopped; swap and timezone are baked in at launch, so changing them later
is a manual in-guest step, not a relaunch.

Toolchain: the VM OS is a shell — editor, git, host CLIs, coding agents, Docker.
App language runtimes (PHP/Laravel, Python/Django, Vue, Go, Node/TS app stacks) run
in Docker Compose, not on the host — do not add them to mise or apt. A system
language toolchain goes on the VM only when a *host* tool needs it. Install priority
for anything new on a VM: mise → official one-liner → documented apt repo → distro
package; add it the way "## mise toolchain" describes (source config + `mise.lock`
in one push). Macs are shells *for* the VM — duplicating a tool on a Mac is an
ergonomics choice, not something to strip.

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

## GitHub MCP servers (per-machine, on purpose)

`run_onchange_after_40-claude-mcp-sync` registers the shared MCP servers
(context7, shadcn-ui, citra, codebase-memory) on every machine with Claude.
`run_onchange_after_41-opencode-mcp-sync` upserts the same shared servers into
`~/.config/opencode/opencode.jsonc` on every machine, plus Figma / Gmail /
Google Calendar on personal-role machines. Other OpenCode config keys are left
alone. Restart OpenCode after apply; then `opencode mcp auth figma` (and
gmail / google-calendar) for the OAuth remotes.
`run_onchange_after_43-codex-mcp-sync` registers the same shared servers with
Codex, including the role-specific GitHub server via the same 1Password PAT
path used by Claude. Its Playwright and Postgres entries share the browser
install and DB-port caveats described below.

The `github` (github.com) and `github-enterprise` (github.foodics.com) servers
differ by client:

- **OpenCode:** no PAT in the file. Script 41 always upserts a local
  `github-mcp-server` entry whose token is `{env:GITHUB_TOKEN}` (work also sets
  `GITHUB_HOST`). That env var already lives in unmanaged `~/.zshrc.local` for
  mise.
- **Claude:** PAT is written into `~/.claude.json` via `claude mcp add`.
  Unattended apply skips when 1Password isn't reachable — each needs a personal
  access token, and the sync script logs `skip` to `chezmoi-health` and moves on
  (the unattended `chezmoi apply` can't unlock 1Password).
- **Codex:** PAT is written into its user config via `codex mcp add` using the
  same 1Password item as Claude; unattended apply has the same non-fatal skip
  behavior when 1Password is unavailable. `codex mcp add` preserves Codex's
  model and per-project trust settings.

**The user's one-time part for Claude** — per identity, not per machine — is to
store the PAT in 1Password:

| server | 1Password item (field `credential`) | token for |
|---|---|---|
| `github` | `GitHub PAT (personal)` | github.com |
| `github-enterprise` | `GitHub PAT (foodics)` | github.foodics.com |

**To register Claude's GitHub MCP on the current machine** (personal role →
`github`, work role → `github-enterprise`; it follows the chezmoi `role`):

```
mcp-github-register
```

That script checks `op` is unlocked, reads the right PAT, and does an idempotent
remove-then-add. By hand it is:

1. `op whoami` — if it errors, unlock: `eval "$(op signin)"` or open the desktop
   app, then retry.
2. `claude mcp remove github --scope user 2>/dev/null` then
   `claude mcp add github --scope user -e GITHUB_PERSONAL_ACCESS_TOKEN="$(op read 'op://Private/GitHub PAT (personal)/credential')" -- github-mcp-server stdio`
   (work: `github-enterprise`, the `(foodics)` item, and add
   `-e GITHUB_HOST=https://github.foodics.com`).
3. `claude mcp list | grep -i github` — confirm.

**When an AI should offer this:** the user wants a GitHub MCP tool on a machine
where `claude mcp list` doesn't show it, or `chezmoi-health` shows
`skip 40-claude-mcp-sync github…` and the user wants it resolved. Point them at
`mcp-github-register`; if it reports `op` locked, that is the user's step to do.
OpenCode does not need that helper — it reads `GITHUB_TOKEN` from the
environment.

<!-- codebase-memory-mcp:start -->
# Codebase Knowledge Graph (codebase-memory-mcp)

When working in a codebase that is indexed by codebase-memory-mcp, prefer its
graph tools over grep, globbing, or file search for code discovery:

1. `search_graph` — find functions, classes, routes, and variables
2. `trace_path` — inspect callers and callees
3. `get_code_snippet` — read specific function or class source
4. `query_graph` — run complex graph queries
5. `get_architecture` — obtain a high-level project summary

Fall back to text search for string literals, error messages, configuration,
non-code files, or when the graph is insufficient.
<!-- codebase-memory-mcp:end -->
