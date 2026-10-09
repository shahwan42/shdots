# Checkpoint: <task>

Context only. Live state, current instructions, and human authorization win.
Do not record credentials or session material. Link large artifacts.

## Intent and decisions

- Outcome:
- Accepted scope:
- Exclusions:
- Deferred choices:
- Authority links (PRD, glossary, principles, decisions):
- Decision sources (who said it, where):

## Checkout and revisions

- Repository / worktree:
- Branch and head:
- Target ref and SHA (the pull request's actual base):
- Pull request URL:
- Original stack-parent SHAs (if stacked):
- Unrelated changes to preserve:

## Authorization

- Human source, permitted action, and limits:
- Pending review requests and execution mode at checkpoint (re-check live mode on resume):
- Unresolved approval boundaries (for example merge):

## Resources and proof

- Record one row for every relevant resource, including borrowed, shared, or
  uncertain resources. Use `task-created`, `borrowed`, `shared`, or `unknown`;
  do not infer ownership from a matching port, path, process ID, or name.

| Resource                    | Exact locator | Owner (task / account / host) | Classification | Live identity proof | Intended disposition | Last verified result |
| --------------------------- | ------------- | ----------------------------- | -------------- | ------------------- | -------------------- | -------------------- |
| Process or port             |               |                               |                |                     |                      |                      |
| Browser target or recording |               |                               |                |                     |                      |                      |
| Worktree                    |               |                               |                |                     |                      |                      |
| Database                    |               |                               |                |                     |                      |                      |
| Artifact                    |               |                               |                |                     |                      |                      |

Include the identity details required by the resource type:

- **Process and port:** original session handle; PID, start time, and
  executable when available; process-group membership only when established.
  A port records usage, never ownership.
- **Browser and recording:** use the browser-driving record for endpoint,
  exact target ID, expected page, ownership, recording path, and controller
  status.
- **Worktree:** repository, exact path, branch and head, and whether this task
  created or borrowed it.
- **Database:** host and account, generated database names, and Worktrunk
  identity. Never store connection credentials.
- **Artifact:** exact task-related paths, producer status, preservation
  destination, and verification result. Include checkpoints, CI results, and
  failed-run evidence.

- Browser ownership notes:
- CI: head, base, result:
- Evidence paths and inspection/upload status:
- Remaining blockers:

## Next action

- Stage:
- Last verified (timestamp):
- Next action:
- Completes when:
