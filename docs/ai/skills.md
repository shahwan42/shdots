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

Imported from the user-wide installation on 2026-10-12. The installer records
[`mattpocock/skills`](https://github.com/mattpocock/skills), each upstream path,
and a folder hash; it does not record an upstream commit. These are installed
snapshots, not a claim of byte-for-byte verification against a commit.
The installer lock remains account-local and is not managed by chezmoi.

All 37 imported skills have Claude adapters except `code-review`, which
collides with Claude's built-in command. `tdd` is excluded because it collides
with a project skill. Installer-owned Caveman, browser-harness, herdr and
find-skills copies remain outside this import.

| Skill | Upstream path | Installer skillFolderHash |
|---|---|---|
| `ask-matt` | `skills/engineering/ask-matt` | `d6a0d9bf3cdc78cbfcbd6466ac5fd3deffb52877` |
| `chief-of-staff` | `skills/in-progress/chief-of-staff` | `22d9deee06f8fe60b752ea386c5fa50312aa15c3` |
| `claude-handoff` | `skills/in-progress/claude-handoff` | `57d198aca08eddccb113632d52c6c13f1f3066ac` |
| `code-review` | `skills/engineering/code-review` | `fee7bb5fdddc069d58cbea09b2c36b5a859eac05` |
| `codebase-design` | `skills/engineering/codebase-design` | `07ba1cd60efc12d0d3a083005c1d9651cf15e39a` |
| `diagnosing-bugs` | `skills/engineering/diagnosing-bugs` | `5fdd6cc53385395441910b026c72d71768e993d4` |
| `domain-modeling` | `skills/engineering/domain-modeling` | `ea30ee454ba264543dbe40737973b1a5afb9f0e6` |
| `git-guardrails-claude-code` | `skills/misc/git-guardrails-claude-code` | `ceed97af09633b300826d0ca0b1464c527ec9a35` |
| `grill-me` | `skills/productivity/grill-me` | `3df14e2d3a89459bf300614be9247e3ce74798f8` |
| `grill-with-docs` | `skills/engineering/grill-with-docs` | `eedaf2562c83155115e9c649fa3ecaac2e10e81d` |
| `grilling` | `skills/productivity/grilling` | `28aceb4c9567b985cb47f7db88cf23c9f33af8b8` |
| `handoff` | `skills/productivity/handoff` | `ce24892bd2d4b9e7fd5ac9b95c03175e18bef388` |
| `implement` | `skills/engineering/implement` | `4804b466ab26c9b9d8d42917547db133d1f20a9f` |
| `implement-spec` | `skills/engineering/implement-spec` | `0cfefc751d0cb64f0c948ffcb17e13b94e778f08` |
| `improve-codebase-architecture` | `skills/engineering/improve-codebase-architecture` | `39bd9cc130f7dfcc4e3ea0b3613f6ebed0d0ad2b` |
| `loop-me` | `skills/in-progress/loop-me` | `a0dfdc3562686d920900973b50289b36e2f7eafe` |
| `migrate-to-shoehorn` | `skills/misc/migrate-to-shoehorn` | `0aea91a3599a4bf7aeec17e3262d4cbcfcbeec23` |
| `pr` | `skills/engineering/pr` | `00b896d811adffad747c7ca30078d909d60c7f93` |
| `prototype` | `skills/engineering/prototype` | `e41d92e171f074a2b6887d8f6faca4a15c83d1ca` |
| `research` | `skills/engineering/research` | `0a6796c5667e95ed2301ba7381c123b4acb2ae1a` |
| `retro` | `skills/engineering/retro` | `335c1862a43da9d629abafdb79ca0c0de118be08` |
| `scaffold-exercises` | `skills/misc/scaffold-exercises` | `44a0ee332b9d67ebbd59389c7eb4e5aff1ce845c` |
| `setup-matt-pocock-skills` | `skills/engineering/setup-matt-pocock-skills` | `aafaabf96fa3945d8a4069317a7a6d36b7169670` |
| `setup-pre-commit` | `skills/misc/setup-pre-commit` | `5b63f9f665bacc9be04cae51982e9ef1469d6699` |
| `setup-ts-deep-modules` | `skills/in-progress/setup-ts-deep-modules` | `b32508a8a7d62c07d32d7c5cff84d357719def7f` |
| `teach` | `skills/productivity/teach` | `3fd617b610e59acbb99644de1ef37e394ff53cd1` |
| `to-questionnaire` | `skills/productivity/to-questionnaire` | `46dfbeeba12a9e52eef446676f42e7551023d9a9` |
| `to-spec` | `skills/engineering/to-spec` | `136b9651747cfccbfbb7c50a6b0dfb757e7547d2` |
| `to-tickets` | `skills/engineering/to-tickets` | `2dee20ad722a31c04ededf9f2d83842473573045` |
| `triage` | `skills/engineering/triage` | `4cb951d62ecccaed601cdc5f9a1b7b3d8a799635` |
| `wait-what` | `skills/productivity/wait-what` | `c8b050e6b8c711be1a9008ceacb2126914f0763e` |
| `wayfinder` | `skills/engineering/wayfinder` | `32b0ce970b1394ede47116e1d3e07f9ccc87591f` |
| `wizard` | `skills/engineering/wizard` | `e396d3ba97c723a78ffd350fb14a3c409137b306` |
| `writing-beats` | `skills/in-progress/writing-beats` | `3a28fb076fdaaec0927080718abb98fc0f340011` |
| `writing-for-agents` | `skills/productivity/writing-for-agents` | `ad2925850efb8973a72d2e666f7a975f9a2d4a9b` |
| `writing-fragments` | `skills/in-progress/writing-fragments` | `98e500e0097ec80f52f6a024c5a2ff6d15235bdb` |
| `writing-shape` | `skills/in-progress/writing-shape` | `ac92229646fccf7315ae139c37b479b3790617f2` |

`agents/openai.yaml` files are imported metadata. This sync uses the installed
contents, including their replacement of the earlier local `code-review` and
`handoff` adaptations and the domain-modeling rename from `CONTEXT` to `GLOSSARY`.

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

The `agent-continuity` reference `references/discovery.md` is the single discovery reference: tool
choice per question type, identity, completeness, and response-shape recipes. The
baseline (`ai-baseline.md`, `codebase-memory.md`) and continuity section 5 point to it;
keep the details there. Its recipes were checked on 2026-10-09 against the
codebase-memory-mcp tool schemas. Recheck them when those schemas change.

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

`to-spec`, `to-tickets`, and `setup-matt-pocock-skills` are now imported.
Repos configure their own tracker through the setup skill. `tdd` still needs a
non-clashing name (for example `test-driven-development`) before it can return.
See `docs/plans/ai-tooling-followups.md`.

## Upgrading a vendored skill

1. Pick an upstream commit, then fetch the skill directory at that commit
   (`gh api repos/mattpocock/skills/contents/<path>?ref=<sha>`, or a shallow
   clone).
2. Replace `dot_agents/skills/<name>` with it, and re-apply the adaptations
   listed above.
3. Review `git diff`, update the commit and hash in this file, then run
   `chezmoi apply`.
