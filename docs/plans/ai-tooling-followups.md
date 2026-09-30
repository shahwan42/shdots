# AI tooling consolidation — deferred parity work

Phase 1 (branch `chore/ai-tooling-consolidation`) set up the shared instruction
baseline, the portable skill source, the Claude symlink adapters, and the
normalized tool ownership. See "AI tooling layout" in `AGENTS.md` and
`docs/ai/skills.md`. The items below were deliberately left out of that phase.
as-dev is migration input only; nothing here requires copying its generated
state.

Priority: **P1** fixes a live gap or a correctness risk, **P2** improves parity,
**P3** is optional.

## P1

- **Codebase Memory Claude agents and hooks.** as-dev has three Codebase Memory
  Claude agents and hook gates/reminders. Decide which ones are portable. Then
  add them as chezmoi source with role/kind gates, not as copies of the VM's
  generated files.
- **Postgres MCP divergence.** Scripts 40 (Claude) and 43 (Codex) hard-code the
  TCMS dev URL through `@modelcontextprotocol/server-postgres`. Script 41
  (OpenCode) uses `postgres-mcp` from mise with `{env:DATABASE_URI}`. Pick one
  server and one config source, then apply it to all three.
- **Stale `~/.codex/skills/browser-harness`.** It is an older copy of
  `~/.agents/skills/browser-harness`, and Codex reads both, so the name is
  listed twice. Delete it after confirming nothing reinstalls it there.
- **codebase-memory installer writes `~/AGENTS.md`.** Its guidance block now
  lives in `.chezmoitemplates/codebase-memory.md`. On a fresh machine, the
  installer (script 40) may append a new `~/AGENTS.md` that holds only that
  block. Check this and, if it happens, remove or suppress the file.

## P2

- **`to-spec` / `to-tickets` and the Matt Pocock workflow as a whole.** They
  depend on `/setup-matt-pocock-skills` and `docs/agents/issue-tracker.md`.
  Import them only together with a per-project tracker convention.
- **Remaining VM-only skills** (about 30 in as-dev `~/.agents/skills`, for
  example `grill-me`, `grilling`, `wayfinder`, `prototype`, `triage`, `teach`,
  and the `writing-*` family). Review each against the tranche-1 criteria:
  self-contained, general, no tracker or plugin machinery.
- **OpenCode command/agent duplication.** Caveman writes `commands/` and
  `agents/` under `~/.config/opencode`, and `~/.config/opencode/skills`
  duplicates `~/.agents/skills` for the seven Caveman skills. Decide whether
  the OpenCode copies should go once OpenCode reads `~/.agents/skills` directly.
- **`find-skills` divergence.** It is owned by `npx skills`, and the Mac and VM
  copies differ. Either pin it with `npx skills add` in a run-script or drop
  it.
- **Caveman skill selection differs by machine.** Both machines pin Caveman
  `v2.6.0`. as-dev has the release's full skill set (`caveman-discover`,
  `caveman-explore`, `lean-build`, `surgical-patch`, and others) in
  `~/.agents/skills`. The Mac installs only script 44's `--skill` subset.
  Decide which of the extra skills belong in that list. `v2.7.0` exists, and
  bumping to it is a separate reviewed change.
- **Work VM coverage.** Script 44 runs only where personal tools live, so
  `fdx-dev` does not get `investigate-first`, `safe-refactor`,
  `verify-and-stop`, or `migration`. Vendor them, or split the skill install
  out of the Caveman gate.
- **OpenCode on the work VM may load the baseline twice.** Script 44 is
  personal-only, so `fdx-dev` has no Caveman `~/.config/opencode/AGENTS.md`.
  OpenCode then falls back to `~/.claude/CLAUDE.md` (which holds the baseline)
  as well as the `instructions` baseline file. Check this on `fdx-dev`. If it
  is confirmed, render a minimal global OpenCode `AGENTS.md` there, or set
  `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT`.
- **Global `tdd` shadows `cashflow-api`'s project `tdd` in OpenCode.** OpenCode
  reads project `.claude/skills`, but in `cashflow-api` `tdd` resolved to
  `~/.agents/skills/tdd`. Claude is unaffected, because it has no `tdd`
  adapter; Codex is unaffected, because it does not read `.claude/skills`. The
  fix belongs to the project (for example, mirroring the skill to
  `.agents/skills` if OpenCode prefers that location), or renaming the global
  skill.
- **Linear and Pencil MCP are not declared in chezmoi.** Linear comes from a
  claude.ai connector. Pencil writes `~/.config/opencode/opencode.json` itself
  (the Pen.app binary path). Both are Mac-native and work today. Only declare
  them if a new Mac needs them without manual setup.
- **MCP inventory as data.** Scripts 40, 41, and 43 repeat the shared server
  list. A `.chezmoidata` inventory that each script ranges over is safe only if
  `chezmoi execute-template` output stays byte-identical per script.

## P3

- **moshi-hook** (as-dev Claude hook). Evaluate before porting.
- **frontend-design plugin.** Install it per machine through `/plugin` if
  wanted. Do not vendor it.
- **typesafe plugin.** Same as frontend-design.
- **`~/Code/.agents/skills/typesafe-ai` ownership (as-dev only).** It lives in
  no repository (`~/Code` is not a git repo). Decide on a home: the owning project repo, or
  `dot_agents/skills` if it proves general.
- **Mise codex leftovers.** Phase 1 uninstalled the out-of-band mise codex
  versions on as-host. Check any other Mac for `codex = "latest"` drift with
  `chezmoi status`.
