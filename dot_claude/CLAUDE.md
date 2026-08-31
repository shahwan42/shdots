@~/Developer/browser-harness/SKILL.md
@~/.claude/rules/mermaid-validation.md

## Output for humans

Any output a human will read — chat replies, PR titles and bodies, commit messages, review comments, reports, Slack/Jira/Confluence posts, docs written for people — is **concise and human-friendly by default**. Lead with the outcome; add supporting detail only where it changes what the reader does next. Prefer plain prose in short sentences to walls of bullets, headers on short answers, file-by-file narration, or restating what a diff already shows. Spell out terms instead of shorthand the reader has to decode.

Two things always win over concision: **mandated formats** (a skill's PR-body or review-report template, commit trailers, CI-validated fields) are followed as specified, and **evidence is never elided** — failing-test output, error messages, and reproduction steps stay complete.

A PR body is the sharpest case, because it is read by a reviewer deciding whether to approve. Hold the part above the first collapsed block to roughly 250 words of prose — the ticket link, the problem, what the change does about it, and a diagram wherever there's a mechanism worth seeing (prefer one to another paragraph; check the rendered body afterwards, since an unparseable fence shows as an error box). Diagrams and a template's fixed lines are free — prose spends the budget in any form, bullets and table cells included — and a one-line change gets a one-line body. Fold depth — evidence tables, production numbers, rejected alternatives, review findings, follow-ups — into `<details>` blocks with summary lines specific enough to skip on, leaving a blank line after each `</summary>` or the table inside renders as literal text. What the reviewer needs in order to approve stays visible, as does anything another person must act on (deploy order, rollback steps, a downstream team's dependency); folding is not a licence to keep writing, and whatever nobody needs isn't in the body at all. A template's `What` / `Why` is a ceiling for the visible part, not a floor — and where a repo ships its own PR template or a skill mandates sections, keep them and apply this inside them.

## Low-cognitive-load chat output (Ahmed's standing preference)

Chat replies are consumed under heavy cognitive load. Structure every substantive reply as:

1. **TL;DR first** — 1–2 sentences, the outcome/decision only.
2. **Short blocks, not paragraphs** — ≤3 sentences per block; a diagram for any flow, dependency, or before/after; tables for comparisons. In terminal chat, diagrams are ASCII/text by default (mermaid doesn't render there); publish a rendered Artifact link only when a diagram is too complex for ASCII. Mermaid stays the format for PR bodies and docs where it renders.
3. **Challenge markers** — explicitly flag ⚠️ assumptions made and ❓ decisions Ahmed should question, so he knows where to push back instead of auditing everything.
4. **Depth on demand** — omit or collapse detail; expand only when asked.

This governs chat replies. Mandated formats (PR bodies, commit messages, skill templates) keep their own rules.
