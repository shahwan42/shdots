# Expect repair validation — 2026-10-08

Validated on macOS with native `codex-cli 0.160.1`, Node 24.21.0, pnpm 10.29.1,
Expect 0.1.3 at `39e97500725783490136a8fc7040e6e4dbaafa44`, and maintained
`@agentclientprotocol/codex-acp@2.1.1`. Private runtime:
`39e975007257-6667e3dae772-284ac2147fe8`. No Claude fallback was used.

## Browser acceptance

| Scenario | Result | Elapsed |
| --- | --- | --- |
| Three consecutive healthy Codex counter runs | Exit 0 each, two executed steps, retained Count: 1 screenshots | 90.631s, 80.368s, 87.008s |
| Same expectation on broken counter | Exit 1, two passed steps and one failed step, screenshot Count: 0 | 81.837s |
| Controlled native app-server exit | Exit 2, original diagnostic and native exit 7 retained, no survivors | 13.984s |
| Browser opened, then deliberately stalled | Exit 124, screenshot retained, no survivors | 46.586s with 45s deadline |
| Cancellation after browser screenshot | Exit 130, screenshot retained, no survivors | 53.916s |
| Disposable FMS flow through Codex | Exit 0, six executed steps, saved plot survives navigation/reload, no survivors | 252.582s |

Healthy screenshots were inspected; all three have SHA-256
`98e3f0915af5a37756dbf4744f4e18abc7daee4141b7febad796416d986d84f6`.
Healthy and broken fixture source remained unchanged during verification.
Preflight deadline and cancellation were also checked separately (8.000s and
7.874s); these are distinct from the browser-phase cleanup checks above.

The controlled early-exit diagnostic was:

```text
EXPECT_SYNTHETIC_ADAPTER_EXIT: controlled app-server failure, status 7
```

Evidence stays ignored under the FMS verification worktree's `.ai-output/expect/`:
`smoke-accepted-1` through `smoke-accepted-3`, `broken-final`,
`early-exit-release`, `deadline-browser`, `cancel-browser`, and `fms-verified-final`. Each includes
raw output, result metadata, and available reports/artifacts. Failed intermediate
attempts remain separate and were not counted as passes.

## Checks and rollout

Fourteen runner regressions pass, covering classification, malformed and trailing
output, PNG corruption, unexpected native exit, intentional native replacement,
terminal provider errors, harmless error-tag text, deadline/cancellation, detached
children, and detached groups whose leaders have exited. Patched-source tests pass:
21 deterministic agent tests, including three operation-guard tests, and 16 artifact
extraction tests. Agent typecheck/lint and CLI/browser typechecks pass. A clean
private build from the pinned source, patch, and frozen lockfile succeeded.
Known upstream SDK declaration-export warnings remain; they did not prevent the
build or browser runs. The live-provider test suite was stopped and is not claimed
as a passing full suite.

The supported skills removal command removed only installer-owned Expect. Other
installer lock entries remained unchanged. Scoped chezmoi rendering, dry-run, and
application passed; the replacement skill and Claude symlink are discoverable.
A fresh native Codex agent identified the managed Expect skill. Configuration,
authentication, global Expect 0.1.3, and browser-harness fingerprints were unchanged.
The repository secret scan found no leaks. Runtime dependencies, credentials,
sessions, and browser evidence are not tracked.

## Additional confirmed findings

Initial completed reports omitted artifact paths because maintained ACP emits
`mcp.browser.close` and nested MCP text results. The patch handles that actual
shape and retains execution events. Native early exit initially lost stderr behind
an unhandled stdin EPIPE; the run-only preload now forwards the cause and records
native status while allowing deliberate provider replacement.

Native shutdown diagnostics can follow completed JSON on verbose stdout. Parsing
now accepts exactly one complete report followed by logs and rejects ambiguous or
malformed output. A later attempt hit a real Codex usage limit and waited through
the deadline despite a terminal native error. The runner now preserves terminal
native error messages and stops promptly with exit 2; a focused regression proves
this in under four seconds. Acceptance resumed after the usage window reset.

Unrelated MCP authentication/startup and marketplace-update warnings were visible
in successful runs. They are retained diagnostics, not evidence that Expect failed.
The historical irrigation stall remains undiagnosed; this repair does not assign
its browser-cancellation errors a new cause.

The FMS flow used the worktree origin `http://localhost:29725` and isolated test
data. It verified empty plots, rejected an empty name, created
“حوشة اختبار Expect” with area 5.5, and verified persistence after navigation and
reload. The final screenshot was inspected. Both disposable fixtures were removed
and their credential file deleted after verification. The first completed FMS
report included a skipped entry for explicitly excluded project checks; the runner
rejected it. One retry after correcting the instruction completed all six steps.

FMS main advanced during verification. Rebuilding generated contracts and migrating
only the owned browser test database aligned the local environment with that head.
The refreshed local CI gate initially failed inventory `Picker Open` with
`expect(element).toBeDisabled()`; the isolated story file passed all nine tests and
a subsequent full gate passed. This is a confirmed intermittent baseline assertion,
not a change made by the Expect documentation integration. Both gate results remain
in `.ai-output/local-ci/`.
