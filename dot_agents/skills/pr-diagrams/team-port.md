# Porting PR diagrams into a team repository

Prompt for an agent working in the target repository. The rule itself is [`SKILL.md`](SKILL.md) (sections "Choose the views" through "Done when"); port it, adapting every concrete detail to the repository: paths, layers, terminology, deploy process. Keep the rule itself the same.

## Decisions already made by Ahmed

Do not reopen these:

1. The rule lives in the repository, so every agent that reads its instructions follows it. One owner document holds the rule, for example `docs/pull-request-diagrams.md`. The agent instructions file (`AGENTS.md`, `CLAUDE.md`, or equivalent) gets a one-sentence pointer. Other documents only point to the owner document.
2. The view table is a menu, not a quota.
3. The overview stays visible; a rollout someone must act on stays visible; every other view is folded in its own `<details>` block.
4. Before/after pairs are part of the rule.
5. The worked example comes from a real merged PR in the repository. If no merged PR exercises a view, leave that view out of the example and say so.

## Adapting the rule

- In "Draw from the diff", name the repository's real migration directory, schema files, and contract or API schema location.
- Drop a table row only when the repository cannot have that subject at all (no database means no ER row). Add a row only for a subject the product has that the table misses.
- Inline the Mermaid validation steps in the owner document (teammates do not have Ahmed's `CLAUDE.md`): write one diagram without its fence to a scratch `.mmd` outside the repo, run `mmdc -i x.mmd -o x.svg`, require exit 0, and require `grep 'Syntax error in text' x.svg` to find nothing.
- Drop the line "When the repository has its own PR-diagram document, it wins" — the owner document is that document.

## Worked example

Pick one real merged PR that touches several layers and has at least one complex operation or a data change. Draw only the views its subjects earn: overview, sequence zoom-in, ER data change, and rollout where they apply. Take the rollout from the repository's actual deploy documentation. Explain in one or two sentences why each skipped view was skipped. If the PR only adds things and reshapes nothing, say it needs no before/after pair.

## Steps

1. Read the repository's agent instructions, contribution or PR rules, PR template, deploy docs, and two or three recent PR bodies (`gh pr list --state merged`, `gh pr view <n> --json body`). Note where the owner document and pointers belong, and the repository's branch, review, CI, and commit rules — those win wherever they differ from this prompt.
2. Choose the worked-example PR. Read its diff (`gh pr diff <n>`) and the current code; collect real names, error codes, migrations, and deploy steps.
3. Load the `writing-for-agents` skill, then write the owner document and the pointers.
4. Validate every diagram, then run the repository's formatting, link, and CI checks.
5. Follow the repository's review gate. If it has none, run one read-only adversarial reviewer on correctness and consistency: the example against the code, the rule against existing instructions for contradictions or quota-like wording. Verify every finding, fix it, re-review the fixed areas.
6. Open the PR. By the rule itself, a documentation-only PR body carries no diagram. Check the owner document's rendered page on GitHub in a foreground tab.
7. Leave the PR unmerged. Report the PR link, the checks run, and open decisions to Ahmed.

## Gotchas from the first rollout

- **Placeholder fences.** A `sequenceDiagram ...` placeholder inside a quadruple-backtick markdown sample is illustrative; exclude it when extracting fences to validate.
- **Unrelated test failures.** Flaky tests can fail a full CI run on a docs-only change. Read the failing test and rerun; leave unrelated code alone.

## Hard rules

- **Commit signing stays on.** If signing fails, stop and report the error.
- **No AI attribution** in commits or PR bodies.
- **Branch and PR only**; the default branch receives nothing directly.
