# Mermaid diagram validation

Every mermaid diagram you generate — any type (flowchart, sequence, state, ER, class,
gantt, pie, …) in any output (chat replies, markdown files, SDDs, Confluence/Jira pages,
PR bodies) — MUST be validated with the mermaid CLI before you deliver it. Validate each
fence separately.

How to validate:

1. Write the fence contents (one diagram only, no ```mermaid fence) to a scratch `.mmd`
   file in a temp/scratchpad dir — never inside the repo. Don't point `mmdc` at the
   `.md` file itself: markdown mode exits 0 even when nothing was validated.
2. Run `mmdc -i diagram.mmd -o diagram.svg`. Valid = exit 0 **and** the SVG does not
   contain `Syntax error in text` — some diagram types (pie, notably) exit 0 while
   embedding that error graphic. Check: `grep -q 'Syntax error in text' diagram.svg`
   → match means INVALID despite exit 0.
3. On non-zero exit, read the error before touching the diagram:
   - Parse error → fix the diagram source, re-run until valid.
   - Tooling error → fix the environment, not the diagram. `mmdc` missing:
     `brew install mermaid-cli` (macOS) or `npm i -g @mermaid-js/mermaid-cli`.
     "Could not find chrome-headless-shell (ver. X)": run
     `npx -y puppeteer browsers install chrome-headless-shell@X` (expected on first
     run and again after every brew upgrade of mermaid-cli — the pinned browser
     version churns; the install is a large one-time download).
4. If validation is genuinely impossible in the environment (no shell, nothing
   installable), explicitly flag the diagram as unvalidated where it appears — never
   present it as checked.
5. Deliver the exact validated text verbatim. If you edit a diagram after validating —
   even a label — validate again.

Version-skew caveat: mmdc passing is necessary, not sufficient. GitHub, Confluence, and
FigJam pin different mermaid versions (Confluence's plugin lags most). Prefer
conservative, widely-supported syntax; avoid bleeding-edge features and quote node
labels containing parentheses, slashes, or other special characters.
