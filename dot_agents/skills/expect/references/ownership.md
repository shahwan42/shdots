# Ownership

This CLI skill derives from millionco/expect's MIT skill version 2.0.0, installed
on the former personal VM before 2026-10-08. The installed skillFolderHash
and original source reference are recorded in shdots `docs/ai/expect-check.md`.
Its broad automatic browser-facing invocation remains in place; its commands and
failure handling are adapted to the managed runner. The upstream MCP-first workflow
is not imported.

shdots owns `~/.agents/skills/expect`; Claude reads the standard adapter at
`~/.claude/skills/expect`. Codex and OpenCode discover the shared directory natively.

For migration, inspect the installer lock, then use `npx skills remove expect
--global --yes` only when Expect is listed as
installer-managed. Let the installer update its lock. Apply only the managed
Expect skill, Claude adapter, runner, and runner assets from the shdots worktree.
Preserve other skills, global Expect, Codex settings and authentication, and the
browser-harness installation. Read shdots `docs/ai/expect-check.md` for the exact
scoped rollout and validation recipe.
