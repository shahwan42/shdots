## Codebase Knowledge Graph (codebase-memory-mcp)

When working in a codebase that is indexed by codebase-memory-mcp, prefer its
graph tools over grep, globbing, or file search for code discovery:

1. `search_graph` — find functions, classes, routes, and variables
2. `trace_path` — inspect callers and callees
3. `get_code_snippet` — read specific function or class source
4. `query_graph` — run complex graph queries
5. `get_architecture` — obtain a high-level project summary

Fall back to text search for string literals, error messages, configuration,
non-code files, or when the graph is insufficient. For project identity, empty
results, pagination, and fallback, read
`~/.agents/skills/agent-continuity/references/discovery.md`.
