# Resource cleanup and handoff

Use this recipe when finishing a task or transferring it to another owner. The
checkpoint is the inventory, not proof by itself: verify each identity against
the live checkout or resource before acting. Keep browser recovery in
[browser-driving](../../browser-driving/SKILL.md), and use the project's own
evidence and database procedures for those resources.

## 1. Reconcile the inventory

Read the checkpoint and confirm the task's scope, current authorization, and
exact resources. Verify live checkout, branch, and head; process identity and
session; browser endpoint, target ID, expected page, and controller status;
database host/account, names, and Worktrunk identity; and artifact paths and
producer status.

A cached PID, matching port, shared working directory, or missing worktree
directory does not establish ownership. Mark uncertain resources as
`unknown`, retain them as unresolved, and continue with independent cleanup.

## 2. Finish producers and release owned runtime resources

Finish recordings and save their output before closing the relevant context.
Let CI and evidence runners perform their own cleanup; wait or cancel through
each runner's original interface. Stop task-created processes through their
recorded sessions first. Before signaling a PID or process group, reverify the
process identity and group membership immediately before the action. A port is
evidence of usage, not ownership.

Use the existing browser-driving recovery to close verified task-created
targets and restore changes this task applied to borrowed targets. Leave shared
browsers and services running.

## 3. Preserve artifacts before retirement

Use the project's evidence archive procedure for evidence runs. Copy every
other required task artifact to a unique destination outside all worktrees,
then verify both file coverage and SHA-256 checksums. Preserve checkpoints, CI
results, failed-run evidence, and outputs from completed producers. Exclude
credential stores, environment files, authentication caches, session material,
and unrelated tasks.

The default account-local destination is
`${XDG_STATE_HOME:-$HOME/.local/state}/fms/task-archives/`. Create a unique
task directory with private permissions and no automatic expiry. Keep the
checkpoint at its current authoritative path when that path survives retirement.
If the checkpoint is inside the worktree, verify an external copy and make it
authoritative before removal; update that copy with the final disposition after
retirement. A failed copy or verification blocks worktree removal.

## 4. Retire only the identified worktree

Before removal, inspect tracked, untracked, and required ignored files. From a
surviving checkout of the same repository, run Worktrunk against the exact
branch and wait for completion:

```sh
wt remove --foreground --no-delete-branch <branch>
```

Keep the branch while its pull request is open or integration is uncertain.
After integration is verified, use normal branch cleanup:

```sh
wt remove --foreground <branch>
```

Do not use force flags or directory-based `--reap` in this recipe. Removal runs
in the background by default, and `--reap` selects processes by working
directory rather than task ownership; see [Worktrunk removal](https://worktrunk.dev/remove/).

## 5. Verify and record the disposition

Confirm the target Worktrunk registration and path are gone, identified owned
processes and browser targets have ended, archives are readable and verified,
and development databases remain retained. Record released, restored, retained,
transferred, and unresolved resources separately. Update the authoritative
checkpoint with the final disposition and each resource's last verified result.

Make cleanup repeatable: recognize completed actions and reverify identity
before acting again, so a replacement process, target, or worktree is never
mistaken for the original resource.

## Handoff

Retain resources the next owner needs and record the new owner, exact locator,
identity proof, and intended disposition. A handoff record carries context; it
does not grant new authorization. The receiving owner verifies current state
and their authority before releasing anything.
