---
name: stacked-prs
description: "Manage stacked PRs with gh stack: create a stack, rebase a stack, or merge a stack safely."
---

# Stacked PRs with `gh stack`

Use the `github/gh-stack` extension. Keep one clone and one worktree per stack;
`gh stack rebase` updates the stack's clean owning worktrees.

## Create and review

1. Initialize with explicit branch names, then add each layer:
   `gh stack init --base <trunk> <bottom-branch>` and
   `gh stack add -Am "<message>" <next-branch>`.
2. For each layer, fetch its parent and pass the repository's local gate against
   that parent (for example, `pnpm ci:local --base origin/<parent>`). Review every
   layer before creating any PR. After fixes, rebase the stack if needed.
3. Write a body file per layer. Push new branches, then create draft PRs from
   bottom to top with `gh pr create --draft --base <parent> --head <branch>
   --title "<title>" --body-file <body-file>`.
4. Before `gh stack submit --auto`, inspect the remote branch tips. It registers
   the PRs as a GitHub stack and pushes branches; get explicit human approval
   first if it would change any already-published branch. `push`, `sync`, and
   `submit` all write to the remote and may force-push.
5. After review, mark each PR ready with `gh pr ready <PR#>`.
6. Run the repository's final review against each PR's actual parent. Get the
   human's explicit approval before merging: `gh stack merge <PR#> --yes --squash`.
   This merges every layer from the bottom through that PR without prompting.
   Before `gh stack sync --prune`, get approval for any force-push it will make
   to remaining published branches; it also deletes local branches for merged PRs.

## Never

- Run a bare `gh stack merge`: in a non-interactive session it merges the whole
  stack without asking. The default merge method is a merge commit.
- Use two clones for one stack. A stale clone's `sync` can overwrite newer
  rebased branch tips.
- Trust `gh stack sync`'s exit code alone. On v0.2.0 it can exit 0 and say
  “Stack synced” after a push failure. Check for a push warning, then compare
  `git rev-parse <branch>` with `git ls-remote --heads origin <branch>` for each
  rebased branch.
- Force-push a published stack branch without explicit human approval. Inspect
  the target branch tips before any `push`, `sync`, or `submit` that can update
  existing remote branches.

## Recovery

- **Failed `add` left an orphan branch checked out:** inspect `git status`, switch
  to the stack top with `gh stack top`, and delete only the orphan created by the
  failed command with `git branch -D <orphan>`. Run `git reset` only if the
  interrupted add left no user changes in the index.
- **A tracked branch was deleted outside `gh stack`:** run `gh stack unstack
  --local`, then reinitialize from the surviving branches in bottom-to-top order:
  `gh stack init --base <trunk> <branch-1> <branch-2> ...`.
- **A merge stopped partway through the stack:** inspect merged/open PRs and their
  bases on GitHub. If `gh stack unstack` leaves stale local tracking, clear only
  that metadata with `gh stack unstack --local`; link the remaining open PRs into
  a fresh stack with `gh stack link <PR#> <PR#> ...` after checking their order.

## Version and verification

Behavior above was checked on `github/gh-stack` v0.2.0 on 2026-10-06. Recheck
the installed version with `gh stack --version` and `gh extension list` after an
upgrade. In a disposable repository, verify whether a bare non-TTY merge skips
confirmation and whether a failed sync push can still exit 0; never test either
behavior in a working project.
