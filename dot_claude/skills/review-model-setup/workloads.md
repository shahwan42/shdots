# Workloads — Ahmed

Repos root: `REPOS=~/Code/foodics` (two levels: `<area>/<repo>`; `cashflow/` is itself a repo).

Baseline observed 2026-11-12 (Claude Code 2.1.311). Treat it as the hypothesis to test, not the answer.

| Tier | Work on it | Where it is set today | Benchmarks that matter |
|---|---|---|---|
| Orchestrator (main loop) | long sessions in the desktop app, planning, delegation, judging agent reports, user conversation | Desktop app model picker (transcripts: mostly `claude-opus-5-5`); `settings.json` `model: sonnet` is the CLI default only; `modelSettings`: Opus `xhigh`, Sonnet `medium` | long-horizon agentic, METR horizon, tau2, instruction following, long-context; input-token price |
| Advisor | reviewer model consulted by the main loop | `settings.json` `advisorModel: opus` | reasoning, instruction following, long-context |
| Executor / investigator / verifier | Laravel feature + bug work (pay, capital, cashflow), Sentry/Datadog/prod investigation, feature verifiers, e2e moderate/advanced chains | repo agents `*-investigator`, `*-feature-verifier`, `*-e2e-orchestrator`: `model: opus`, no effort pin | SWE-bench, Terminal-Bench, tool-use reliability, cost per task |
| PR reviewers + RFC steward | money-moving code review, RFCs | `pay-pr-reviewer`, `capital-pr-reviewer`, `pay-rfc-steward`: `opus` + `effort: xhigh`; capital-admin/console `pr-review` skills pass `model: "opus"`; pay review gate requires Fable/Mythos/Opus | bug-finding precision, SWE-bench, instruction following |
| Writer / estimator | Jira ticket writers, estimators, sprint demo, pay-support | repo agents: `model: opus`, no effort pin | writing quality, instruction following, factual accuracy |
| Runner / probe | e2e `basic` chains, login/health helpers, scripted sweeps | pay: `pay-e2e-basic-chain` Opus `effort: low`; capital: `config.md` routes `basic` + helpers to `sonnet` (no pin → Sonnet `medium`) | tool-call reliability, cost per task, speed |
| Test automation | Playwright planner/generator/healer, principal SDET (capital-automation, -v2) | agents: playwright-* `sonnet`, principal-sdet `opus`, no pins | tool-use reliability, browser/OSWorld, cost per task |
| Fable (unexplained) | 1,316 `claude-fable-5-2` subagent records in the 7 days to 2026-11-12, from capital-api and pay sessions; no inventoried file declares Fable | unknown — first run must trace the source | decide whether it becomes a named escalation tier or is drift |
