---
name: pencil-workflow
description: >-
  Use for Pencil/pen.dev canvas work and `.pen` inspection, editing, recovery, saving,
  export, or validation.
---

# Pencil workflow

Use the current Pencil tools and their instructions. A `.pen` extension alone does not
establish how a file is stored; follow the repository's validated format and the active
tool's schema.

## Preflight and route

1. Resolve the requested file and inspect the repository's current worktree changes.
   Check `pen version` and the relevant CLI or tool help. If the CLI is missing or
   authentication fails, report the exact diagnostic and required user action. Do not
   install tools, inspect credential files, or change authentication.
2. Call Pencil `get_app_state()` once during preflight. If it reports the exact requested
   path as the active document, use Pencil MCP. A different or unopened canvas, or a
   connection error, routes to headless mode. Do not keep retrying desktop dialogs.

## Headless access

Create a unique task scratch directory and quote every path, including paths with spaces.
Record the input hash before starting and confirm it is unchanged afterward. Keep the
input read-only and work in a persistent terminal session:

```sh
pen interactive --in "$input.pen" --out "$scratch/working.pen"
```

Use the output path for all changes. Preserve the terminal session until save, reopen, export, and inspection are complete.

## Native instructions and edits

Before operating, read `read_skill()`, `read_skill({ path: "pen-schema.md" })`, and
`read_skill({ path: "execute.md" })` from the active Pencil tools. Then inspect
`get_app_state()` and only the relevant nodes. Do not copy a schema into this skill.

Follow the transport's argument shape: Pencil MCP `execute` requires its `filePath`; the
interactive CLI injects the current file path, so its calls omit that argument.

Call `save()` explicitly. If an `execute` snippet fails, recover with its returned
`editId` and `edits`; do not resend the original snippet. Inspect current state before
replaying mutations, then confirm the intended change occurred once and did not create
duplicate nodes.

After saving, inspect shared component IDs and references and verify explicit defaults
such as `layoutIncludeStroke` where shared components exist. If a save removes an explicit
value, compare the original and saved component and inspect its export; do not assume
omission preserves the prior behavior. Keep the output in scratch when equivalence is
unclear.

## Reopen and verify

Reopen the saved output in Pencil and confirm the intended edit survived. Export the
affected frames through Pencil and inspect the PNG for clipping, text, right-to-left
physical ordering, and layout. Compare the scratch diff because saving can normalize a
document; copy work back only after visual and structural review shows no unintended
changes. Run the repository's checks against the saved representation.

Close only sessions created for this task. Use a repository-defined non-native fallback
only within its documented limits. Never assume every `.pen` file is encrypted or plain
JSON based on its extension or another tool's generic warning.
