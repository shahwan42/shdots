{{ template "output-preferences.md" . }}
{{ template "mermaid-validation.md" . }}
{{ template "codebase-memory.md" . }}
{{ template "worktrees.md" . }}

## Version overlap and rollback

For work where two versions can read or write the same data (rolling deploys,
runtime rollback, cached older clients), state the compatibility claim before
implementing and prove it for the exact versions tested. Follow
`~/.agents/skills/migration/references/compatibility-proof.md`; read it directly,
as the Claude `migration` skill may come from the Caveman plugin without it.

## Discovery

Read `~/.agents/skills/agent-continuity/references/discovery.md` when a question spans
code, text, chat history, and external tools; when a tool signature is unknown; or
when a result is empty, paginated, or truncated.

## Authentication diagnostics

For MCP authentication questions, use `ai-tools-doctor` inventory and its structured report; see
`~/.local/share/chezmoi/docs/ai/authentication-diagnostics.md` for the safe workflow. Prefer
version/help and supported status checks. A live probe can start a server, so stop when the
doctor reports missing authentication or approval. Never print credential stores, session
caches, cookies, environment dumps, resolved configuration exports, credential-bearing command
arguments, raw logs, response bodies, or tracebacks. Keep the stage, reason code, outcome,
numeric codes, counts, timings, and a value-free reproduction step.

{{ template "agent-shell.md" . }}
