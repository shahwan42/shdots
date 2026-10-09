# Authentication diagnostics

Use this workflow to identify the failed authentication stage and record a useful summary
without inspecting credentials or publishing arbitrary tool output. This work is diagnostic
only: it does not change authentication, register credentials, rotate tokens, or run login or
logout flows.

## Start with safe evidence

Check the client version and help first:

```sh
codex --version
codex mcp --help
claude --version
claude mcp --help
opencode --version
opencode mcp --help
```

Use `ai-tools-doctor` for MCP inventory and its private report directory:

```sh
ai-tools-doctor
ai-tools-doctor --client codex --client claude --client opencode
```

Inventory shows configuration evidence. It does not prove that a server connects. A live
`--probe` can start a local server and make the doctor's reviewed smoke call. Run it only when
the user wants a live connection check and the server is configured, approved, and safe to
start. The doctor stops before launching a server when authentication or approval is missing.
Record the required client action and stop that probe; do not run login or logout as part of
diagnosis.

Prefer version/help and supported status interfaces. Do not paste raw output from
`codex mcp list --json`, `opencode debug config`, or `claude mcp get` into a chat, issue,
checkpoint, screenshot, or report. These commands may expose resolved configuration or start a
server. Route inventory through `ai-tools-doctor`, which parses exports internally and reports
selected metadata.

## Keep these values out of evidence

Never print, copy, or persist credential stores, OAuth/session caches, cookies, environment
contents, resolved client configuration, or credential-bearing command arguments. Do not
include provider messages, server-supplied descriptions, response bodies, stderr, raw logs, or
tracebacks. Redaction is a backup check for approved metadata; it is not a safe way to publish
arbitrary output.

Inventory may show credential-related key names and whether a value is present. It may show
unresolved variable names. Neither is permission to display the corresponding values.
Structured doctor reports are private files with mode `0600` in a directory with mode `0700`;
share only the fields needed to explain the outcome.

## Record the failure

Include the client and server, mode (`inventory` or `probe`), stage, outcome, reason code,
numeric HTTP/protocol/exit code when present, elapsed time, counts, and a reproduction command
with values withheld. A useful summary looks like this:

```text
Client/server: <client>/<configured server>
Mode/stage: probe / connection
Outcome/reason: auth_required / http_401
Code: HTTP 401
Elapsed/counts: <reported values>
Reproduction: ai-tools-doctor --probe --client <client> --server <configured server>
Required action: authenticate in the owning client, then retry only if requested
```

Keep the doctor's `reason_code` and outcome unchanged. Unknown failures stay failures with
`unexpected_failure`; do not replace them with a guess based on an exception message.

OAuth login is a separate operation. Codex documents `codex mcp login <server-name>` for
servers that support OAuth in its [official MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
Authentication setup is outside this diagnostic workflow.

Known credential exposure follow-ups and their unverified rotation status are tracked in
[`docs/plans/ai-tooling-followups.md`](../plans/ai-tooling-followups.md). Preventing future
output does not resolve a past exposure.
