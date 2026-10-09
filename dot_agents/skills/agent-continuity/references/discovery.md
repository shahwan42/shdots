# Discovery

Choose the tool for the question, retrieve bounded evidence, check identity and
completeness, then answer or run one targeted follow-up. Stop once the answer has
sufficient evidence.

```text
Question → Authority → Suitable tool → Bounded retrieval
         → Identity and completeness check → Answer or targeted follow-up
```

## Route

| Question | First route | Done when |
|---|---|---|
| Symbols, callers, relationships | Graph: confirm the project matches the checkout, `search_graph`, `trace_path`, bounded `get_code_snippet` | Cited source read; `check_index_coverage` `freshness` is not `metadata_changed`/`missing`, or the live file confirms the snippet |
| Error text, configuration, docs, literals | Search the files directly; filename discovery when the location is unknown | Hit read in context; widen scope only if the first scope was insufficient |
| Current or archived chat history | Native index and reader: select conversations, follow cursors, read needed turns | Conversation identity matches and the needed turns are read |
| Supported external operation, unknown tool capability | Purpose-built tool, API, or CLI; focused `--help` or schema when the signature is unknown; capability search only where one is provided | Signature confirmed before the call |
| Interactive or visual work | `browser-driving`, `pencil-workflow`, computer-use for native dialogs; repeatable checks live in project-local tests | Per that skill |

Authentication questions follow `ai-tools-doctor` and the baseline's
authentication diagnostics. Keep stage, reason, outcome, codes, counts, timings, and
a value-free reproduction; exclude credential material and raw responses.

## Identity

Graph project IDs and Codex saved-project IDs are separate namespaces. List the
projects (`format: json` keeps full `root_path` values; tree output abbreviates them)
and pick the entry whose `root_path` is the checkout; a repository basename does not
derive either ID (`farm_management_system` indexes as
`Users-as-Code-side-hustle-fms-repos-farm_management_system`, a dated example).
`list_projects` pages (`limit`, `offset`, `has_more`, `next_offset`): follow the
cursor until the match appears. A search hit for a title or ID may be a document that
quotes it; open the conversation itself to confirm.

## Completeness

Keep `total`, `returned`, `has_more`, `next_offset`, `truncated`, and cursors with
every result. Page sequentially with the returned mechanism, one page at a time.

An empty result proves nothing until scope, filters, and coverage are checked.
`check_index_coverage` with the exact paths returns per path `status`
(`no_recorded_issue`, `excluded`, `coverage_unavailable`), `freshness`
(`metadata_match`, `not_tracked`, `metadata_changed`, `missing`), and
`recommended_action`; `coverage[].kind`/`detail` name the reason (for example
`not_indexed_file` / `gitignore`). Treat every status as best-effort, and a stale or
unavailable one as a prompt to read the live source. Fall back to a targeted live
search of the path:

```sh
rg -n 'literal' path/to/exact-file   # an explicit file is searched even when ignored
rg -n --no-ignore 'literal' dir/     # directory scans skip ignored files without the flag
```

## Response shape

Tool results arrive as a string, a direct object, or an MCP envelope
`{content:[{type:"text",text}], isError}`. Check the shape before reading a field;
report anything else by shape and keys only.

```js
function unwrap(resp) {
  if (typeof resp === "string") {
    try { return { shape: "json-string", value: JSON.parse(resp) }; }
    catch { return { shape: "text", value: resp }; }
  }
  if (resp && Array.isArray(resp.content)) {
    const text = resp.content.filter((c) => c?.type === "text").map((c) => c.text).join("\n");
    try { return { shape: "mcp", isError: !!resp.isError, value: JSON.parse(text) }; }
    catch { return { shape: "mcp", isError: !!resp.isError, value: text }; }
  }
  if (resp && typeof resp === "object") return { shape: "object", value: resp };
  return { shape: "unknown", type: typeof resp };
}

// Chat turns: user text can sit in content[], assistant text in `text`
// (retrospective observation; confirm against the reader's schema).
function messageText(m) {
  if (typeof m?.text === "string") return m.text;
  if (typeof m?.content === "string") return m.content;
  if (Array.isArray(m?.content))
    return m.content.map((c) => (typeof c === "string" ? c : c?.text ?? "")).join("\n");
  return "";
}

// Independent reads: keep every success, report every failure.
const settled = await Promise.allSettled(reads);
const ok = settled.filter((s) => s.status === "fulfilled").map((s) => s.value);
const failed = settled.flatMap((s, i) => (s.status === "rejected" ? [{ i, reason: String(s.reason) }] : []));
```

Never spread an unknown string (it becomes characters) or recursively print every
string in a payload.

## Bounded output

- Select fields before emitting: identity (project, qualified name, file, lines), the
  decisive text, and the completeness metadata.
- Mark excerpts partial; fetch more evidence when the answer needs it.
- Select chat turns by role explicitly. A page of tool-only messages can hold no user
  or assistant text (a 4-message page returned only a result line); page back by
  cursor instead of concluding the session is empty.
- Honor the reader's maximum page size (the retrospective's 100-thread request hit a
  50 cap; unverified here).
- Store complete relevant non-sensitive failure evidence in an artifact; show the
  decisive part.

## Execution discipline

- Set the working directory explicitly for every shell command.
- Searching a known location: name the exact path, since directory scans skip ignored
  files.
- Run only independent reads in parallel, and inspect every result.
- Run pagination and shared-state operations (index, checkpoint, worktree) sequentially.

## Verified

Checked 2026-10-09 against codebase-memory-mcp and `rg` in this environment. Claims
marked unverified were not exercised.

| Recipe | Evidence |
|---|---|
| Graph, snippet, source compare | `search_graph` (`name_pattern: cleanupCandidates`, `format: json`) returned `total: 1`; `get_code_snippet` for its qualified name matched `scripts/lib/worktree-env.mjs` lines 76–91 |
| Empty filtered query | Same name with a non-matching `file_pattern` returned `total: 0` and a hint; the unfiltered query finds the symbol |
| Coverage | On the FMS project, `check_index_coverage` gave the source file `status: no_recorded_issue` and the ignored retrospective `status: excluded` (`coverage[].detail: gitignore`); another project returned `coverage_unavailable` with `freshness: metadata_changed`, which the Coverage section documents |
| Text search | `rg` on the exact ignored retrospective path found the target row; `README.md` lookup of `ci:local` hit line 56 |
| Reader pages | `list_events` returned a cursor and a page with no conversational text; `before_uuid` reached assistant text. `search_session_transcripts` matched a document quoting a title, not the conversation |
| Response handling | Fixtures for string, object, MCP envelope, unexpected shape, paginated result, and a rejected parallel read passed (run from the code block above, outputs matched) |
| Native Codex/ChatGPT thread readers | Unverified here: those tools were not in this session. Confirm their schema and message shapes before relying on `messageText` |
