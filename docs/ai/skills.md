# Portable AI skills

Portable skills live in `dot_agents/skills/<name>` and render to
`~/.agents/skills/<name>`. Codex and OpenCode read that directory natively.
Claude reads selected skills through symlink adapters in
`dot_claude/skills/symlink_<name>` → `../../.agents/skills/<name>`.

Claude Code discovers symlinked skill directories. This was verified on
2026-09-30 with Claude Code 2.1.285: a temporary probe skill linked this way
appeared in the `skills` list of the `claude -p --output-format stream-json`
init event.

`~/.agents/skills` has other writers: the Caveman installer (script 44),
`npx skills` (`find-skills`, `.skill-lock.json`), herdr
(`herdr-gpui-browser`), and browser-harness. Do not make `dot_agents/skills` an
`exact_` directory, and do not manage `.skill-lock.json`.

## Locally authored skills

| Skill | Source | Claude adapter |
|---|---|---|
| `pencil-workflow` | `dot_agents/skills/pencil-workflow` | yes |
| `agent-continuity` | `dot_agents/skills/agent-continuity` | yes |

`pencil-workflow` is model-invoked so Pencil and `.pen` work can discover it
automatically.

`agent-continuity` is also model-invoked, covering resumption after interruption
or handoff, user scope corrections, and resource cleanup that preserves evidence.
It is a guide with a checkpoint template and cleanup reference; it has no
checker, hooks, or memory system. The agent verifies live state itself. Projects
choose the checkpoint location.

## Vendored skills

### From mattpocock/skills

Source: [`mattpocock/skills`](https://github.com/mattpocock/skills) at commit
`c55ee46073ed923f86ce59a5eb3b6d895095d1b7`. The skills were installed on as-dev
with `npx skills` on 2026-09-19 and imported from there on 2026-09-30. Every
file was checked byte-for-byte against that upstream commit. The only
differences are the adaptations listed below.

| Skill | Upstream path | skillFolderHash (as-dev lock) | Claude adapter |
|---|---|---|---|
| code-review | `skills/engineering/code-review` | `d8e341cee7980127dddda05159bedf25dc853615` | no: collides with Claude's built-in `/code-review` |
| codebase-design | `skills/engineering/codebase-design` | `344e3efc88ee60663b2e989555c2efdb548fbd42` | yes |
| diagnosing-bugs | `skills/engineering/diagnosing-bugs` | `99bd56983e42bc752c52da67f1112e4121781cd1` | yes |
| domain-modeling | `skills/engineering/domain-modeling` | `388c9822641805ca2dcd5038e68a1d5282437ee5` | yes |
| handoff | `skills/productivity/handoff` | `2242e8f05424b8c2ae94194a90d97b88d16108ec` | yes |
| implement | `skills/engineering/implement` | `f07d230f645fc9ac390cf13a450bbff12ad791a3` | yes |
| implement-spec | `skills/in-progress/implement-spec` | `1ec4cd3fbcc62d57cd32cf1d907c4c4761355e2b` | yes |
| research | `skills/engineering/research` | `0a6796c5667e95ed2301ba7381c123b4acb2ae1a` | yes |
| resolving-merge-conflicts | `skills/engineering/resolving-merge-conflicts` | `77f0d7de3143abbf03e55a63522d30bff31ae908` | yes |
| writing-for-agents | `skills/productivity/writing-for-agents` | `ad2925850efb8973a72d2e666f7a975f9a2d4a9b` | yes |

Adaptation of `code-review`: `code-review/SKILL.md` no longer tells the user to run
`/setup-matt-pocock-skills` when `docs/agents/issue-tracker.md` is missing. It
uses a documented tracker workflow if the repo has one, then falls back to the
tracker CLI (such as `gh issue view`), and otherwise skips issue references.

`agents/openai.yaml` in each skill is upstream Codex metadata, not generated.

Local adaptation of `handoff` (2026-10-08): it now exports the
`agent-continuity` checkpoint sections, references a maintained checkpoint
instead of copying it, and recommends skills by portable name and readable path
instead of a provider-specific "Skill tool". Its manual-only policy
(`disable-model-invocation`, `allow_implicit_invocation: false`), metadata, and
OS temporary-directory export are unchanged. The generic skill validator rejects
`argument-hint` and `disable-model-invocation`; keep them and validate through
the supported hosts. Re-apply this adaptation on upgrade.

### From Caveman

Source: [`JuliusBrussee/caveman`](https://github.com/JuliusBrussee/caveman)
`v2.6.0` (`b82c0ad42c2bedc1f2cd78e414dadfaffbaaeec3`), `skills/<name>/`.
Byte-identical except the local `migration` adaptation below. The same release that script 44 pins.

| Skill | Claude adapter |
|---|---|
| investigate-first | only where Caveman is not installed (work VMs); elsewhere the `caveman` plugin provides `caveman:investigate-first` |
| safe-refactor | same |
| verify-and-stop | same |
| migration | same |

They are vendored rather than installed by script 44, because they are plain
engineering workflows (no Caveman Cloud, no credentials, no paths), and script
44 runs only where personal tools live. Vendoring gives every machine,
including work VMs, the same copy. When script 44's Caveman pin moves, re-copy
them from the new tag.

Local adaptation of `migration` (2026-10-09): `SKILL.md` gains one bullet
pointing to `references/compatibility-proof.md`, a locally authored recipe for
version-overlap and rollback proof. `ai-baseline.md` also points agents at the
installed file path directly, because Claude on personal accounts loads
`caveman:migration` from the plugin, which lacks the reference. Plugin
ownership, adapters and invocation policies are unchanged. On upgrade, re-copy
from the new tag, then re-apply the bullet and keep the reference file.

`browser-harness` is not vendored: the browser-harness install writes the
canonical copy to `~/.agents/skills/browser-harness` (newer releases print it
with `browser-harness skill`). Claude gets a symlink adapter only where that
file exists (`.chezmoiignore.tmpl` uses `stat`). Script 49
(`run_onchange_after_49-codex-skill-dedupe.sh.tmpl`) renders only once the
canonical copy exists, then removes the older `~/.codex/skills/browser-harness`
on that apply, so Codex lists it once.

## Locally authored companions

`browser-driving` is maintained here in `dot_agents/skills/browser-driving`,
with a standard Claude symlink adapter. It supplies verified call recipes and
task ownership/resumption rules alongside the installed `browser-harness` skill;
it does not vendor or replace that skill. Its ChatGPT reference loads only for
webpage interaction. Automatic discovery remains enabled.

Recipes were checked against installed browser-harness 0.1.13 on 2026-10-08.
When upgrading the harness, inspect its installed signatures and recheck the
recipes on a disposable mobile fixture; follow the linked upstream recovery
guidance rather than copying its manual into this companion.

## Expect

`expect` is shdots-owned, with the standard Claude adapter. Its CLI workflow,
source patch, private runtime, migration, and acceptance evidence are documented
in [Expect runner](expect-check.md). Upstream MCP-first instructions are not imported.

## Name clashes with project skills

Project skills must win. Neither Claude nor OpenCode guarantees that:

- Claude runs a personal skill (`~/.claude/skills`) over a project skill
  (`.claude/skills`) with the same name.
- OpenCode resolved `tdd` to `~/.agents/skills/tdd` inside
  `foodics/repos/cashflow/cashflow-api`, over that project's `.claude/skills/tdd`.

So a global skill must not use a name that any project defines. `tdd`
(mattpocock `skills/engineering/tdd`, skillFolderHash
`79288be15c67b849f22b6572056601090fd20913`) was removed from the global set on
2026-09-30 for this reason; `implement` still mentions `/tdd`, which resolves
to the project's skill where one exists. Before adding a global skill, check:

```sh
find ~/Code -maxdepth 7 -not -path '*/node_modules/*' \( -path '*/.claude/skills/<name>' \
  -o -path '*/.agents/skills/<name>' -o -path '*/.opencode/skills/<name>' \
  -o -path '*/.claude/commands/<name>.md' \)
```

## Deferred

`to-spec` and `to-tickets` need the tracker setup from
`/setup-matt-pocock-skills`. `tdd` needs a non-clashing name (for example
`test-driven-development`) before it can return. See `docs/plans/ai-tooling-followups.md`.

## Upgrading a vendored skill

1. Pick an upstream commit, then fetch the skill directory at that commit
   (`gh api repos/mattpocock/skills/contents/<path>?ref=<sha>`, or a shallow
   clone).
2. Replace `dot_agents/skills/<name>` with it, and re-apply the adaptations
   listed above.
3. Review `git diff`, update the commit and hash in this file, then run
   `chezmoi apply`.
