---
name: expect
description: Optional exploratory browser check for one named risk that project stories and tests can't reach cheaply, such as URL or refresh state, concurrent edits, unusual input, or mobile layout. Not a default step after browser-facing changes; prefer deterministic stories or tests for fault paths you can control. Diagnose Expect failures and retain browser evidence.
license: MIT
metadata:
  author: millionco
  version: "2.0.0-shdots.2"
---

# Expect

Use the shdots-owned `expect-check` runner for an optional exploratory check of a
named risk. It adds evidence; it never replaces project stories, tests or local CI.
It privately builds pinned Expect source with the maintained Codex adapter. See
[provenance and rollout](references/ownership.md) when installing or updating it.

1. Run `expect-check doctor`. A missing or mismatched runtime requires
   `expect-check setup`, then a successful doctor. Setup alone installs dependencies;
   ordinary runs never install, update, or select global Expect.
2. Start the affected app using its project recipe. Read its actual origin from
   the active worktree's configuration. Use disposable data and an empty ignored
   output directory for each run.
3. Write explicit acceptance criteria covering the intended behavior and plausible
   failures: invalid inputs, boundary values, rapid submission, navigation, or
   nearby regressions. Require browser actions, a PNG screenshot after the final
   assertion (also on test failure), visual inspection, and browser closure.
4. Run:

   ```sh
   expect-check run --url "$app_origin" --instruction "$instruction" \
     --target changes --output-dir "$ignored_output_directory"
   ```

   Targets are `changes`, `unstaged`, or `branch`. Defaults are Codex, headless,
   no system cookies, and a 300000-millisecond deadline. `expect-check smoke
   --output-dir "$ignored_output_directory"` uses the same path with a disposable
   counter fixture and a 120000-millisecond deadline.
5. Inspect `result.json`, `report.json`, raw stdout/stderr, and the reported
   screenshots. A pass requires a completed report, executed steps, valid retained
   artifacts, and visual evidence that supports the assertions. The runner checks
   artifact structure and hashes; the agent must inspect screenshot contents.

Exit codes: 0 passed; 1 browser test failure; 2 infrastructure or configuration
failure; 124 deadline; 130 cancellation. Original child status is in `result.json`.
A timeout, initialization, navigation alone, or an incomplete report is no pass.
Preserve the exact diagnostic. Correct the concrete cause before retrying once;
if that retry fails, report the unresolved failure and evidence paths.

`--agent claude` is an explicitly reported fallback. It never counts as a Codex
repair acceptance pass. Keep project Storybook, Playwright, local CI, and required
visual captures: Expect provides additional evidence. Browser-driving and
capture automation remain separate workflows.

Runs sharing the private browser runtime are serialized. A busy or stale lock
requires inspecting its recorded owner; remove it only after verifying that owner
is gone. Cleanup belongs to the runner and affects its own process group only.
