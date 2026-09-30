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
`npx skills` (`expect`, `find-skills`, `.skill-lock.json`), herdr
(`herdr-gpui-browser`), and browser-harness. Do not make `dot_agents/skills` an
`exact_` directory, and do not manage `.skill-lock.json`.

## Vendored skills

Source: [`mattpocock/skills`](https://github.com/mattpocock/skills) at commit
`c55ee46073ed923f86ce59a5eb3b6d895095d1b7`. The skills were installed on as-dev
with `npx skills` on 2026-09-19 and imported from there on 2026-09-30. Every
file was checked byte-for-byte against that upstream commit. The only
difference is the adaptation listed below.

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
| tdd | `skills/engineering/tdd` | `79288be15c67b849f22b6572056601090fd20913` | yes |
| writing-for-agents | `skills/productivity/writing-for-agents` | `ad2925850efb8973a72d2e666f7a975f9a2d4a9b` | yes |

Adaptation: `code-review/SKILL.md` no longer tells the user to run
`/setup-matt-pocock-skills` when `docs/agents/issue-tracker.md` is missing. It
uses a documented tracker workflow if the repo has one, then falls back to the
tracker CLI (such as `gh issue view`), and otherwise skips issue references.

`agents/openai.yaml` in each skill is upstream Codex metadata, not generated.

## Installer-owned skills in this tranche

`investigate-first`, `safe-refactor`, `verify-and-stop`, and `migration` come
from [`JuliusBrussee/caveman`](https://github.com/JuliusBrussee/caveman)
`v2.6.0`. Script 44 installs them into `~/.agents/skills` with `npx skills add`,
so they are not vendored here. Their `SKILL.md` files match `v2.6.0` and the
as-dev copies. Claude has no adapter for them, because the `caveman` plugin
already provides them as `caveman:*`. Script 44 runs only where personal tools
live (Macs and personal VMs).

`browser-harness` has a Claude adapter only (Macs). Its target,
`~/.agents/skills/browser-harness`, is written by the browser-harness install.

## Deferred

`to-spec` and `to-tickets` need the tracker setup from
`/setup-matt-pocock-skills`. See `docs/plans/ai-tooling-followups.md`.

## Upgrading a vendored skill

1. Pick an upstream commit, then fetch the skill directory at that commit
   (`gh api repos/mattpocock/skills/contents/<path>?ref=<sha>`, or a shallow
   clone).
2. Replace `dot_agents/skills/<name>` with it, and re-apply the adaptations
   listed above.
3. Review `git diff`, update the commit and hash in this file, then run
   `chezmoi apply`.
