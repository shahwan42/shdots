# Dotfiles maintenance instructions

This home directory is managed by chezmoi. The Git repository at
`~/.local/share/chezmoi` is the source of truth; files such as `~/.zshrc` are
rendered outputs.

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
