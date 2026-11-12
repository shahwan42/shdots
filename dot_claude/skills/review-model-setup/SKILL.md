---
name: review-model-setup
description: Use when a new Claude model ships, Claude pricing or effort defaults change, or the user says "review my model setup", "new Claude release", "which model should orchestrate / execute", "update model tiers", "default effort per model", "is Fable still worth it", or invokes /review-model-setup. Covers user-scope Claude Code config and Foodics repo agents.
---

# Review Model Setup

Adapted from a teammate's shared skill for this machine (chezmoi-managed dotfiles, nested `~/Code/foodics/<area>/<repo>` layout, desktop app, no user agents or hooks).

## Overview

Re-derive every tier from fresh evidence on each release. The current setup is the hypothesis under test, never the baseline to keep. No tier is exempt — including the orchestrator — and no number comes from memory.

Three phases, in order: **research → model per tier → default effort per model**. Then apply, verify, log.

Start by reading `decisions.md` next to this file (if present) and closing any trial whose date has passed.

## 1. Research (parallel, never inline)

Load `claude-api` for IDs, pricing, API effort defaults and breaking changes. Then spawn three subagents in one message (`general-purpose` with `model: "opus"`); each writes `<scratchpad>/bench-<lane>.md` with URL + date per number, effort/thinking config per number, and `UNVERIFIED` on anything not seen on a fetched page.

| Lane | Sources |
|---|---|
| official | anthropic.com/news launch posts, system cards, docs model overview + pricing, engineering blog (agentic coding, multi-agent) |
| independent | SWE-bench Verified/Pro, Terminal-Bench, Aider polyglot, LMArena, Artificial Analysis (incl. cost/task), ARC-AGI, METR time horizon, Vals.ai, LiveBench, Epoch, Scale SEAL, tau2-bench, OSWorld, BFCL, BrowseComp. Say per board if the new model is missing. |
| practitioner | Claude Code docs + changelog (alias resolution, default model, effort — **for the installed version and every version since the last run**), HN, r/ClaudeAI, r/ClaudeCode, practitioner blogs. Tag each claim official / measured / anecdotal. |

If web tools or agents are unavailable (dry run, sandbox, failures): run the inventory, then **halt before phase 4**. Report the missing evidence; do not assign models or efforts.

## 2. Inventory every place a model or effort is set

Read `REPOS` from `workloads.md`. Repos are nested two levels deep, and a parent can itself be a repo (`cashflow/`). Primary checkouts only: a primary has a `.git` **directory**; a linked worktree has a `.git` **file**.

Run in zsh; `(N)` keeps an unmatched glob from aborting the command.

```zsh
REPOS=~/Code/foodics
primaries=()
for d in $REPOS/*/(N/) $REPOS/*/*/(N/); do [[ -d $d.git ]] && primaries+=($d); done
print -l $primaries

claude --version   # effort/alias rules change between versions; check claims against this one
jq '{model, effortLevel, modelSettings, advisorModel}' ~/.claude/settings.json
for p in $primaries; do rg -Hn '^(model|effort):' $p.claude/agents 2>/dev/null; done
for p in $primaries; do rg -Hn -i 'sonnet|opus|fable|haiku' $p.ai/e2e-orchestrator/config.md 2>/dev/null; done
for p in $primaries; do rg -ln "model: *['\"]?(opus|sonnet|fable|haiku)" $p.claude/skills 2>/dev/null; done
rg -L -ln "model: *['\"]?(opus|sonnet|fable|haiku)" ~/.claude/skills -g '!review-model-setup/**'
rg -n -i 'fable|opus|sonnet|haiku|claude-[a-z]+-[0-9]|effort' "$(chezmoi source-path)/dot_claude/CLAUDE.md.tmpl"
```

Record versioned strings (e.g. `claude-fable-5`) — they go stale silently. There are no user-scope agents (`~/.claude/agents`) or hooks (`~/.claude/hooks`) today; if either appears, add it to the inventory.

- **Desktop app.** `settings.json` `model` is the CLI default, not what the main loop runs: the Claude desktop app picks the main-loop model itself. Take the main loop's real model from transcripts (below), not from settings.
- **Spawn vs frontmatter — verify, don't assume.** Sources disagree on whether a spawn-time `model:` keeps the agent's frontmatter `effort:` (the teammate's notes say it does; `pay/.ai/e2e-orchestrator/config.md` says a hand-passed `model` drops the pin). On each run, check one real spawn of each kind in a transcript for the installed Claude Code version, then judge drift. For each skill hit above, compare the model it passes against the frontmatter of the agent it spawns.
- **What actually ran.** Tally the last 7 days, subagents and main loop separately:
  ```zsh
  find ~/.claude/projects -path '*/subagents/*.jsonl' -mtime -7 -print0 | xargs -0 rg -oN --no-filename '"model":"claude-[a-z0-9-]*"' | sort | uniq -c
  find ~/.claude/projects -maxdepth 2 -name '*.jsonl' -mtime -7 -print0 | xargs -0 rg -oN --no-filename '"model":"claude-[a-z0-9-]*"' | sort | uniq -c
  ```
  A model the tiers don't name, or one missing from the tally, is drift — trace which project and workflow spawned it. Also diff `modelSettings` against the latest `~/.claude/settings.json.bak-*` / `.backup.*`: `/effort` persists silently there.

## 3. Workload map

Read `workloads.md` next to this file: the user's tiers, the work on each, and the benchmarks that matter per tier. Decide every tier listed there.

## 4. Choose the model per tier

Every current model is a candidate for every tier — a new Opus competes for orchestrator, a new Sonnet for executor, a top model at `low` effort for runner. For each tier, compare candidates head-to-head on that tier's benchmarks:
- Judge **cost per completed task**, not price per token.
- Evidence says a cheaper model matches or beats the current one → switch.
- Evidence says the current model is clearly stronger on the tier's benchmarks → keep, and state the price premium.
- Evidence missing or split → propose a trial with an exit criterion (duration, what to compare), not a guess.
- Fewer distinct models is a tiebreaker (one prompt cache per model).

## 5. Choose default effort per model

- Read each new model's **API default effort** — it can differ from its predecessor. Check how the installed Claude Code version applies top-level `effortLevel` vs `modelSettings.<exact-model-id>.effortLevel` vs agent `effort:` frontmatter; this has changed between versions.
- Executor, reviewer, investigator: `xhigh` unless evidence shows `high` holds quality.
- Orchestrator: lowest level the evidence supports; it runs the most tokens.
- Runner/probe: `low` or `medium`.
- `max` only where evidence shows headroom above `xhigh`.
- Per-agent `effort:` frontmatter overrides stay only where a tier needs a different level.

## 6. Output contract

Present, in order:
1. **Decision table** — `Surface | Current | Proposed | Evidence (URL) | Confidence`. One row per tier plus one per effort default.
2. **Trials** — tier, candidate, duration, exit criterion.
3. **Diff** — every file change.

Get the user's go-ahead on the table before applying.

## 7. Apply and verify

- `~/.claude/settings.json` (`model`, `modelSettings`, `advisorModel`): edit directly. chezmoi's settings script merges only its own keys and leaves these alone.
- Global CLAUDE.md: edit the chezmoi source (`$(chezmoi source-path)/dot_claude/CLAUDE.md.tmpl`), then `chezmoi apply ~/.claude/CLAUDE.md`. Never edit `~/.claude/CLAUDE.md` directly.
- Repo agents / skills / `config.md`: `git fetch origin`, then `wt switch --create <branch> --base origin/dev`; open a PR with the `pr` skill, labelled `don't merge`. Never merge.
- Verify: `jq . ~/.claude/settings.json`; prove alias resolution by spawning one trivial `Agent(model: "opus")` task, then reading `message.model` from its transcript at `~/.claude/projects/*/<this-session-id>/subagents/agent-*.jsonl` (scope to the session id; a project-wide grep hits old transcripts). Agent-definition frontmatter edits load only in a **new session** — verify those after restart. Never ask a model to quote its own identity line (trips the `reasoning_extraction` classifier and poisons resumes).

## 8. Decision log

Append a dated entry to `~/.claude/skills/review-model-setup/decisions.md` (create it if absent, heading `# Model setup decisions`, newest first): models released, per-tier decisions + one-line reason + key URLs, trials opened. This file is deliberately **not** in chezmoi, so edit it in place; `chezmoi apply` leaves it alone.

## Common mistakes

| Mistake | Fix |
|---|---|
| "New model doesn't touch tier X" | Every tier gets a head-to-head. |
| Stopping at `claude-api` pricing | Pricing is not benchmarks. Run all three lanes. |
| "CLAUDE.md is version-agnostic" without grepping | Grep the chezmoi source for versioned IDs. |
| Counting worktree agents | Primary checkouts only; repo changes go through PRs. |
| Scanning one level of `~/Code/foodics` | Repos are two levels deep. |
| Trusting `settings.json` `model` for the main loop | The desktop app picks it; read transcripts. |
| Missing `config.md` level routing and `effort:` pins | Run the full inventory. |
| Generic effort picks ("mechanical → medium") | Tie each level to evidence or the model's API default. |
