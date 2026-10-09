{{ template "output-preferences.md" . }}
{{ template "mermaid-validation.md" . }}
{{ template "codebase-memory.md" . }}
{{ template "worktrees.md" . }}

## Authentication diagnostics

For MCP authentication questions, use `ai-tools-doctor` inventory and its structured report; see
`~/.local/share/chezmoi/docs/ai/authentication-diagnostics.md` for the safe workflow. Prefer
version/help and supported status checks. A live probe can start a server, so stop when the
doctor reports missing authentication or approval. Never print credential stores, session
caches, cookies, environment dumps, resolved configuration exports, credential-bearing command
arguments, raw logs, response bodies, or tracebacks. Keep the stage, reason code, outcome,
numeric codes, counts, timings, and a value-free reproduction step.

{{ template "agent-shell.md" . }}
