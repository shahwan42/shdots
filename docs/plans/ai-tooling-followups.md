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
- **Codebase Memory hooks on existing machines.** Script 40 now installs with
  `--skip-config`, so a fresh machine gets no Codebase Memory hooks, skills, or
  instruction blocks. Machines configured earlier keep whatever the installer
  wrote then. Decide which hooks are wanted and declare them here.
- **Postgres MCP divergence.** Scripts 40 (Claude) and 43 (Codex) hard-code the
  TCMS dev URL through `@modelcontextprotocol/server-postgres`. Script 41
  (OpenCode) uses `postgres-mcp` from mise with `{env:DATABASE_URI}`. Pick one
  server and one config source, then apply it to all three.
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
- **`tdd` under a non-clashing name.** Removed from the global set because
  Claude and OpenCode let a global skill beat a project skill of the same name
  (`cashflow-api` ships `tdd`). Reintroduce it only under a distinct name,
  such as `test-driven-development`, if the fork is worth it.
- **browser-harness where the canonical skill is missing.** as-dev has only
  `~/.codex/skills/browser-harness` (current content) and no
  `~/.agents/skills` copy; fdx-host runs browser-harness 0.1.0, which has no
  `skill` command and no skill file. Claude gets no adapter on either. Upgrade
  browser-harness there, or install its skill into `~/.agents/skills`; script
  49 then removes the Codex-only copy on the next apply.
- **as-dev still has `npx skills`-owned Matt Pocock copies** (including `tdd`)
  in `~/.agents/skills`, outside chezmoi. They are migration input; prune them
  when the VM-only skills are triaged.
- **Codex doctor `state.rollout_db_parity` warning on as-host.** Codex's own
  thread state; not configuration. Leave to Codex unless it causes problems.
- **Caveman skill selection differs by machine.** Both machines pin Caveman
  `v2.6.0`. as-dev has the release's full skill set (`caveman-discover`,
  `caveman-explore`, `lean-build`, `surgical-patch`, and others) in
  `~/.agents/skills`. The Mac installs only script 44's `--skill` subset.
  Decide which of the extra skills belong in that list. `v2.7.0` exists, and
  bumping to it is a separate reviewed change.
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
