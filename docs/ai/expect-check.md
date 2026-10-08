# Managed Expect runner

`expect-check` uses a private, versioned runtime. Global Expect, Codex configuration
and authentication, and browser-harness remain untouched. Ordinary runs verify the
runtime inventory and never install dependencies. `setup` alone fetches and builds.

## Source and ownership

Expect source: [millionco/expect](https://github.com/millionco/expect), commit
`39e97500725783490136a8fc7040e6e4dbaafa44`, CLI 0.1.3, FSL-1.1-MIT (full license
retained in managed assets). `compat.patch` replaces the legacy adapter in CLI,
agent, and SDK dependencies with exact `@agentclientprotocol/codex-acp@2.1.1`,
uses the existing package-bin resolver, and preserves the bundler exclusion.
The maintained adapter uses the installed native Codex through `CODEX_PATH`;
the runner resolves its real path and records its version each run.

The patch adds a 30-second ACP initialization/session deadline, propagates adapter
exit to pending operations and streams, and preserves stderr. Maintained ACP delta updates retain their tool names and
text results; close-artifact extraction accepts its `mcp.browser.close` name and
nested MCP text results. Execution events are retained alongside artifacts. Browser session
and artifact paths are isolated by environment variables; the private daemon
stays in its parent's process group. Setup also declares the CLI's missing Babel
syntax plugin, needed for a clean build at this revision. The build orders all
CLI workspace dependencies, including the generated browser runtime and SDK.
The complete dependency lock is retained, including package integrity hashes;
setup requires pnpm 10.29.1 and a successful patched-source typecheck and guard test.

The MIT skill derives from installed upstream version 2.0.0, source
`.agents/skills/expect/SKILL.md`, skillFolderHash
`699f7c7ebbafd5872177b70a2a0693c6f939ca38` (installer timestamp 2026-03-25).
Its original command policy is replaced with the corrected CLI workflow; its broad
browser-facing invocation remains. shdots owns the skill and standard Claude
adapter. Upstream's MCP-first policy is not imported. The installer owns its lock.

## Interface and evidence

```text
expect-check setup
expect-check doctor
expect-check smoke --output-dir <empty-directory>
expect-check run --url <origin> --instruction <text>
                 --target <changes|unstaged|branch> --output-dir <empty-directory>
                 [--agent codex|claude] [--timeout-ms <milliseconds>]
```

Defaults: Codex, headless, no system cookies, 300000 milliseconds for feature
runs and 120000 for smoke. Internally the runner calls `expect-cli tui` with
`-u`, `-m`, `-y`, `--output json`, and an execution timeout. It additionally bounds
the entire child lifetime, including initialization and reporting. Shutdown allows
one second for termination before killing owned processes and groups, then checks
for survivors. A run-only Node preload records child PID/start identity and detached
group ownership, including Playwright browser groups. Group ownership survives
leader exit while members remain; unrelated groups are preserved. Native version
preflight is limited to five seconds and the remaining run budget; fixture Git
commands share that budget and disable signing and hooks. A per-account lock serializes private runs; its owner record must
be checked before removing a stale lock. Existing global sessions are not reused.

Output must be empty and Git-ignored when inside a repository. Preserve `stdout.log`,
`stderr.log`, `report.json`, `result.json`, and `artifacts/`. Result metadata includes
origin, instruction, versions, source revision, runtime, elapsed time, original
child exit/signal, runner exit, cleanup checks, and artifact paths/hashes.
A completed report must contain executed steps, consistent exit/status, and valid
retained screenshots. The runner checks paths, PNG structure and hashes; the agent
must inspect screenshot contents before claiming the visible assertions passed.

| Exit | Meaning |
| --- | --- |
| 0 | Completed passing browser test with verified artifacts |
| 1 | Completed failing browser test with verified artifacts |
| 2 | Infrastructure/configuration, missing or inconsistent report/artifacts |
| 124 | Whole-run deadline |
| 130 | Cancellation |

Claude fallback is reported explicitly and cannot satisfy Codex repair acceptance.
Retry once only after correcting a concrete cause. A failure after that correction
remains unresolved; project checks and live inspection are separate evidence.

## Scoped rollout

Inspect both chezmoi source and target status/diff before migration. Preserve
unrelated drift; apply only these targets with `--exclude scripts`:

```sh
source_worktree=<shdots-worktree>
chezmoi --source "$source_worktree" cat ~/.local/bin/expect-check | sh -n
chezmoi --source "$source_worktree" apply --exclude scripts --dry-run --verbose \
  ~/.local/bin/expect-check ~/.local/share/expect-check \
  ~/.agents/skills/expect ~/.claude/skills/expect
```

If the global skills installer lists Expect, remove only that skill using
`npx skills remove expect --global --yes` (all agent links for that named skill).
Let the installer update its own lock, and verify other skill entries are unchanged.
Apply the same four scoped targets, verify scoped chezmoi status is clean, then run
setup and doctor. Never make `~/.agents/skills` exact-managed. Verify discovery in
a fresh Codex agent and the Claude symlink; compare configuration/authentication
and global Expect/browser-harness fingerprints before/after without printing secrets.

## Verification

Run `node --test tests/expect_check.test.mjs`, patched-source checks, a clean setup
from the recorded source/patch/lock, skill frontmatter/link validation, scoped
render/dry-run/apply, and the repository gitleaks pre-commit scan.

Codex acceptance requires three consecutive healthy counter smoke runs, the same
expectation on a broken counter (test exit 1), prompt invalid-config/early-exit
failure retaining its cause, timeout and cancellation with bounded cleanup, and
one disposable FMS flow. The fixture's source must stay unchanged throughout each
run. Inspect screenshots and record runtime and confirmed additional findings.

Historical causes remain distinct. Account naming exposed:

```text
Error: error loading config: /Users/as/.codex/config.toml:6:16: unknown variant `default`, expected `fast` or `flex`
```

This is service-tier parser incompatibility, not reasoning effort. The irrigation
stall remains undiagnosed; closing its browser yielded:

```text
Error: page.evaluate: Target page, context or browser has been closed
```

Equivalent `page.goto` and `page.setViewportSize` errors were cancellation
consequences. They do not establish the stall's cause or a completed Expect pass.
