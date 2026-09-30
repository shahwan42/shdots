## Worktrees

Worktrunk (`wt`) is the standard worktree lifecycle manager. Use it for normal
creation and removal rather than direct `git worktree add` or `git worktree remove`.
Read-only Git diagnostics such as `git worktree list` remain acceptable.

- Create a branch and worktree: `wt switch --create <branch>` (defaults to the repository's default branch).
- Choose a base: `wt switch --create <branch> --base=<ref>`.
- Intentionally start from current HEAD: `wt switch --create <branch> --base=@`.
- Inspect: `wt list`.
- Clean up after merging: `wt remove <branch>`.

The global Worktrunk config owns worktree locations; use its computed paths
instead of inventing directories. Repository-specific lifecycle and setup
behavior belongs in `.config/wt.toml`.
