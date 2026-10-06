---
name: pr-diagrams
description: Pull request diagrams — which Mermaid views a PR body earns, how to draw and place them. Use when writing or editing a pull request body.
---

# PR diagrams

Describe the change visually from the angles a reviewer needs, each drawn with the Mermaid type that fits that angle. One linear happy-path flowchart shows the flow, not what changed or where the risk is.

## Choose the views

The table is a **menu, not a quota**. A view appears only when the change contains its subject and a reviewer needs it. A change with nothing to describe (docs, a typo, a one-line fix) carries no diagram. Skip a view another view already shows, or that the diff shows faster, such as one added optional field. A before/after pair counts as one view.

| Subject in the change | View | Mermaid type | Placement |
| --- | --- | --- | --- |
| Several modules or layers | Overview: touched layers and modules, changes highlighted | `flowchart` | Visible |
| Transaction, lock, retry, race, or another multi-step operation | Zoom-in on that operation | `sequenceDiagram` with `alt`, `opt`, `rect` | Folded |
| Migration: new or changed table, column, constraint, or relation | Data change: changed tables and the tables that explain them | `erDiagram` | Folded |
| New status or lifecycle | Lifecycle | `stateDiagram-v2` | Folded |
| Branching validation or business rule | Decision logic | `flowchart TD` | Folded |
| API or contract shape | Request and response shape | `classDiagram` | Folded |
| Deploy order, rollback, or a stack of pull requests | Rollout | `flowchart LR` | Visible when someone must act, else folded |
| Reshaped mechanism that highlights on the After diagram alone cannot show: a reordered step, moved ownership, a replaced flow, a split table | Before/after pair, in place of a highlighted After-only view of the same subject | Any type above, the same for both | Same as the view it replaces; when folded, both share one block |

When the repository has its own PR-diagram document, it wins over this table.

## Draw from the diff

Diagrams are claims about the diff; a reviewer may check them against the code. Read each one off the change itself:

- **Data change:** from the migrations and schema files in the diff.
- **Zoom-in:** from the entry point, service, and transaction code the request runs through, including its error codes and statuses.
- **Contract shape:** from the contract or API schema the diff touches.
- **Before/after pair:** draw Before from the target branch and After from the PR head.
- **Rollout:** from the repository's deploy documentation or pipeline config, not from memory or an older PR's prose.

Label nodes with real module, table, column, and endpoint names, in the repository's glossary terms where it has one.

## Conventions

- **Highlight changes** in flowcharts with these classes; unchanged nodes keep the default style. A removed node stays in the diagram, marked `removed`, so a removal alone needs no before/after pair. The explicit text colour keeps labels readable in GitHub's light and dark themes.

  ```text
  classDef new fill:#1a7f37,stroke:#116329,color:#ffffff
  classDef changed fill:#9a6700,stroke:#7d4e00,color:#ffffff
  classDef removed fill:#cf222e,stroke:#a40e26,color:#ffffff,stroke-dasharray:5 3
  ```

- **Before/after pairs** are two separate diagrams, Before stacked above After, each with a one-line caption.
  - Same type for both, and the same direction where the type has one.
  - Nodes in both keep the same IDs and labels, so only the real difference stands out.
  - Mark removed nodes `removed` in Before; mark new or changed nodes in After.
  - Sequence and ER diagrams have no classes: mark changes with ER column comments or in the caption.
- **Mark ER columns** with a quoted comment, such as `"new, nullable"` or `"changed: now required"`.
- **Stay small:** about 12 nodes or 10 messages per diagram. Split a bigger picture into two views.
- **Caption** each diagram with one line saying what to look at.
- **Conservative syntax**, because GitHub pins its own Mermaid version:
  - stable diagram types only, nothing ending in `-beta`;
  - quoted labels;
  - commas inside sequence notes and messages (a semicolon ends the statement and breaks the parse);
  - one connected chain instead of unconnected subgraphs, since GitHub may reverse their order (draw rollback as a dotted `rollback` edge off the deploy chain).

## Placement

The overview sits in the visible part of the body, beside the prose it replaces; diagrams do not count toward the prose budget. Each folded view gets its own `<details>` block whose `<summary>` names the view and its point, for example `Sequence: saving output locks the parent row before checking the cap`. Leave a blank line after `</summary>`, or the diagram renders as text.

## Done when

1. Every diagram passed the Mermaid validation in `~/.claude/CLAUDE.md` (one `.mmd` per fence, exit 0, no `Syntax error in text`), re-run after any edit.
2. After pushing, the rendered PR page is open in a foreground tab (background tabs can render Mermaid frames blank), every `<details>` block is expanded, and each diagram renders.

Promoting this rule into a team repository: follow [`team-port.md`](team-port.md).
