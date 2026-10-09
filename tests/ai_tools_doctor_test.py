"""ai-tools-doctor acceptance tests. Run with the doctor's private runtime:

    ~/.local/share/ai-tools-doctor-runtime/venv/bin/python tests/ai_tools_doctor_test.py -v
"""
import contextlib
import hashlib
import http.server
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "dot_local/share/ai-tools-doctor"
FIXTURE = ROOT / "tests/fixtures/ai_tools_doctor_server.py"
sys.path.insert(0, str(PACKAGE))

from ai_tools_doctor import cli, config, context, install, probe, proc, report, skills  # noqa: E402
from ai_tools_doctor.model import ServerConfig  # noqa: E402
from ai_tools_doctor.redact import Redactor  # noqa: E402

GH_TOKEN = "ghp_" + "SyntheticTokenValue0123456789abcd"
PG_PASSWORD = "synthetic-pg-password-91"
PG_URL = f"postgresql://app:{PG_PASSWORD}@db.internal:5432/farm"
HEADER_SECRET = "header-secret-value-77"
QUERY_SECRET = "query-secret-value-55"
STDERR_SECRET = "stderr-secret-value-33"
SHORT_SECRET = "s4!"
ALL_SECRETS = [GH_TOKEN, PG_PASSWORD, HEADER_SECRET, QUERY_SECRET, STDERR_SECRET, SHORT_SECRET]


def write_exec(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o755)
    return path


def sh(version="1.2.3", code=0):
    return f"#!/bin/sh\n[ \"$1\" = --version ] && echo \"${{0##*/}} {version}\" && exit {code}\nexit {code}\n"


def make_ctx(home: Path, path_dirs, kind="mac", role="personal", project=None) -> context.Context:
    env = {"HOME": str(home), "PATH": os.pathsep.join([*map(str, path_dirs), "/usr/bin", "/bin"])}
    return context.Context(home=str(home), env=env, project=str(project or home), kind=kind, role=role,
                           profile_source="test")


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        return os.waitpid(pid, os.WNOHANG)[0] == 0
    except ChildProcessError:
        return True


def stop_and_reap(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.kill()
    process.wait()


class Tmp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(os.path.realpath(self._tmp.name))
        self.home = self.tmp / "home"
        self.home.mkdir()


class OwnershipTests(Tmp):
    def test_version_failures_keep_codes_and_drop_command_output(self):
        ctx = make_ctx(self.home, [])
        secret = "version-output-sentinel-92"
        failed = write_exec(self.tmp / "codex-failed",
                            f"#!/bin/sh\nif [ \"$1\" = --version ]; then echo '{secret}'; exit 23; fi\nexit 0\n")
        check = install.version_of(ctx, str(failed))
        self.assertEqual((check["reason_code"], check["exit_code"]), ("version_command_failed", 23))
        self.assertNotIn(secret, json.dumps(check))
        malformed = write_exec(self.tmp / "codex-malformed",
                               f"#!/bin/sh\nif [ \"$1\" = --version ]; then echo '{secret}'; exit 0; fi\nexit 0\n")
        check = install.version_of(ctx, str(malformed))
        self.assertEqual((check["reason_code"], check["version"]), ("unparseable_version", None))
        self.assertNotIn(secret, json.dumps(check))

    def test_homebrew_codex_native_claude_mise_opencode_pass_on_mac(self):
        brew = self.tmp / "opt/homebrew/bin"
        write_exec(brew / "codex", sh())
        write_exec(self.home / ".local/share/claude/versions/2.1.0", sh("2.1.0"))
        (self.home / ".local/bin").mkdir(parents=True)
        (self.home / ".local/bin/claude").symlink_to(self.home / ".local/share/claude/versions/2.1.0")
        write_exec(self.home / ".local/share/mise/shims/opencode", sh("1.18.0"))
        ctx = make_ctx(self.home, [brew, self.home / ".local/bin", self.home / ".local/share/mise/shims"])
        # Homebrew prefix is fixed in the classifier, so model it by realpath under a Caskroom path.
        cask = write_exec(self.tmp / "Caskroom/codex/0.1/codex", sh("0.160.1"))
        (brew / "codex").unlink()
        (brew / "codex").symlink_to(cask)
        rows, records = install.inventory(ctx, ["codex", "claude", "opencode"])
        self.assertEqual([r["outcome"] for r in rows], ["passed"] * 3, rows)
        self.assertEqual(records["claude"]["owner"], "native")
        self.assertEqual(records["codex"]["owner"], "homebrew")

    def test_missing_executable_fails_with_owner_instruction(self):
        ctx = make_ctx(self.home, [])
        rows, _ = install.inventory(ctx, ["opencode"])
        self.assertEqual(rows[0]["outcome"], "failed")
        self.assertIn("chezmoi apply", rows[0]["next_action"])

    def test_broken_shim_is_a_failure_not_a_pass(self):
        shims = self.home / ".local/share/mise/shims"
        write_exec(shims / "opencode", "#!/bin/sh\necho 'mise ERROR: no version set' >&2\nexit 1\n")
        rows, _ = install.inventory(make_ctx(self.home, [shims]), ["opencode"])
        self.assertEqual(rows[0]["outcome"], "failed")
        self.assertIn("does not run", rows[0]["detail"])

    def test_shadowed_selection_is_wrong_owner_but_inactive_copy_is_fine(self):
        other = write_exec(self.tmp / "opt/other/bin/claude", sh())
        native = write_exec(self.home / ".local/bin/claude", sh())
        ctx = make_ctx(self.home, [other.parent, native.parent])
        rows, records = install.inventory(ctx, ["claude"])
        self.assertEqual(rows[0]["outcome"], "failed")
        self.assertIn("expected native", rows[0]["detail"])
        self.assertEqual(len(records["claude"]["candidates"]), 2)
        # Reverse order: native selected, other is only an inactive copy.
        ctx = make_ctx(self.home, [native.parent, other.parent])
        rows, _ = install.inventory(ctx, ["claude"])
        self.assertEqual(rows[0]["outcome"], "passed")
        self.assertIn("Inactive copies", rows[0]["detail"])

    def test_vm_expects_mise_for_all_three(self):
        shims = self.home / ".local/share/mise/shims"
        for name in ("codex", "claude", "opencode"):
            write_exec(shims / name, sh())
        rows, _ = install.inventory(make_ctx(self.home, [shims], kind="vm", role="work"),
                                    ["codex", "claude", "opencode"])
        self.assertEqual([r["outcome"] for r in rows], ["passed"] * 3)

    def test_project_mise_override_is_intentional(self):
        shims = self.home / ".local/share/mise/shims"
        write_exec(shims / "opencode", sh("1.0.0"))
        pinned = write_exec(self.home / ".local/share/mise/installs/opencode/9.9.9/opencode", sh("9.9.9"))
        project = self.tmp / "proj"
        project.mkdir()
        (project / "mise.toml").write_text('[tools]\nopencode = "9.9.9"\n')
        write_exec(self.tmp / "bin/mise", f"#!/bin/sh\necho {pinned}\n")
        ctx = make_ctx(self.home, [self.tmp / "bin", shims], project=project)
        rows, _ = install.inventory(ctx, ["opencode"])
        self.assertEqual(rows[0]["outcome"], "passed")
        self.assertIn("project mise override", rows[0]["provenance"])


class TruthRegressionTests(Tmp):
    def test_smoke_judge_rejects_plausible_but_wrong_bodies(self):
        from ai_tools_doctor import smoke
        self.assertIsNotNone(smoke.judge("github", '{"message":"Bad credentials"}'))
        self.assertIsNone(smoke.judge("github", '{"login":"someone"}'))
        self.assertIsNotNone(smoke.judge("postgres", 'relation "x" does not exist (line 1)'))
        self.assertIsNotNone(smoke.judge("postgres", "connect ECONNREFUSED 127.0.0.1:5432"))
        self.assertIsNone(smoke.judge("postgres", '[{"?column?": 1}]'))
        self.assertIsNotNone(smoke.judge("codebase-memory", "something unrelated"))
        self.assertIsNone(smoke.judge("codebase-memory", "projects: 1"))
        self.assertIsNone(smoke.judge("codebase-memory", "projects: 1\n  ~/Code/error-tracker"))   # name may say error

    def test_review2_regressions(self):
        from ai_tools_doctor import smoke
        deny = {"deny": ["github_get_me"]}
        self.assertIsNotNone(smoke.blocked_by_client("github", "get_me", deny))
        (self.home / ".claude.json").write_text(json.dumps({
            "mcpServers": {"github": {"type": "stdio", "command": "user-cmd"}},
            "projects": {str(self.home): {}}}))
        (self.home / ".mcp.json").write_text(json.dumps({"mcpServers": {"github": {"command": "project-cmd"}}}))
        servers, _ = config.read_claude(make_ctx(self.home, []))
        self.assertEqual([(s.name, s.command) for s in servers], [("github", "user-cmd")])  # pending one loses
        shims = self.home / ".local/share/mise/shims"
        write_exec(shims / "claude", sh())
        project = self.tmp / "proj"
        project.mkdir()
        (project / "mise.toml").write_text("[tools]\n")
        write_exec(self.tmp / "bin/mise", f"#!/bin/sh\necho {shims}/other\n")
        rows, _ = install.inventory(make_ctx(self.home, [self.tmp / "bin", shims], project=project), ["claude"])
        self.assertEqual(rows[0]["outcome"], "failed")   # mac expects native; a mise copy is not excused

    def test_claude_local_scope_shadows_user_scope(self):
        (self.home / ".claude.json").write_text(json.dumps({
            "mcpServers": {"github": {"type": "stdio", "command": "user-cmd"}},
            "projects": {str(self.home): {"mcpServers": {"github": {"type": "stdio", "command": "local-cmd"}}}}}))
        servers, _ = config.read_claude(make_ctx(self.home, []))
        self.assertEqual([(s.name, s.command) for s in servers], [("github", "local-cmd")])
        self.assertTrue(any("shadows" in n for n in servers[0].notes))

    def test_claude_wildcard_deny_and_enable_all(self):
        (self.home / ".claude").mkdir()
        (self.home / ".claude/settings.json").write_text(json.dumps({"permissions": {"deny": ["mcp__*"]}}))
        (self.home / ".claude.json").write_text(json.dumps({"mcpServers": {"s": {"type": "stdio", "command": "c"}}}))
        servers, _ = config.read_claude(make_ctx(self.home, []))
        self.assertEqual(servers[0].tool_restrictions["deny"], ["mcp__*"])
        from ai_tools_doctor import smoke
        self.assertIsNotNone(smoke.blocked_by_client("s", "get_me", servers[0].tool_restrictions))

    def test_codex_project_tool_restrictions_are_read(self):
        project = self.tmp / "proj"
        (project / ".codex").mkdir(parents=True)
        (project / ".codex/config.toml").write_text('[mcp_servers.github]\ndisabled_tools = ["get_me"]\n')
        restrictions = config.codex_restrictions(make_ctx(self.home, [], project=project))
        self.assertEqual(restrictions["github"]["deny"], ["get_me"])

    def test_known_location_off_path_is_not_selected(self):
        write_exec(self.home / ".local/share/mise/shims/opencode", sh())
        rows, record = install.inventory(make_ctx(self.home, []), ["opencode"])
        self.assertEqual(rows[0]["outcome"], "failed")
        self.assertIn("not on PATH", rows[0]["detail"])

    def test_project_override_cannot_mask_a_wrong_owner(self):
        other = write_exec(self.tmp / "opt/other/bin/opencode", sh())
        pinned = write_exec(self.home / ".local/share/mise/installs/opencode/9.9.9/opencode", sh("9.9.9"))
        project = self.tmp / "proj"
        project.mkdir()
        (project / "mise.toml").write_text('[tools]\nopencode = "9.9.9"\n')
        write_exec(self.tmp / "bin/mise", f"#!/bin/sh\necho {pinned}\n")
        ctx = make_ctx(self.home, [other.parent, self.tmp / "bin"], project=project)
        rows, _ = install.inventory(ctx, ["opencode"])
        self.assertEqual(rows[0]["outcome"], "failed")

    def test_mistyped_server_name_is_not_a_clean_exit(self):
        bins = self.tmp / "bins"
        for tool in ("codex", "claude", "opencode"):
            write_exec(bins / tool, "#!/bin/sh\n[ \"$1\" = --version ] && echo 'x 1.0.0' && exit 0\necho '[]'\n")
        (self.home / ".claude.json").write_text("{}")
        env = {"HOME": str(self.home), "PATH": f"{bins}:/usr/bin:/bin", "PYTHONPATH": str(PACKAGE),
               "PYTHONDONTWRITEBYTECODE": "1"}
        done = subprocess.run([sys.executable, "-m", "ai_tools_doctor", "--kind", "mac", "--probe", "--server", "githb",
                               "--project", str(self.home), "--output-dir", str(self.tmp / "o")],
                              env=env, cwd=PACKAGE, capture_output=True, text=True)
        self.assertIn(done.returncode, (1, 2))


class SkillTests(Tmp):
    def skill(self, root, name, body="x"):
        d = self.home / root / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(body)
        return d

    def test_adapters_to_one_canonical_file_are_not_conflicts(self):
        canon = self.skill(".agents/skills", "tdd", "canonical")
        (self.home / ".claude/skills").mkdir(parents=True)
        (self.home / ".claude/skills/tdd").symlink_to(canon)
        rows, summary = skills.analyze(make_ctx(self.home, []))
        self.assertEqual(summary["adapters"], 1)
        self.assertEqual(summary["conflicts"], 0)
        self.assertTrue(all(r["outcome"] == "passed" for r in rows))

    def test_conflicting_same_name_implementations_fail(self):
        self.skill(".agents/skills", "review", "one")
        self.skill(".claude/skills", "review", "two")
        rows, summary = skills.analyze(make_ctx(self.home, []))
        self.assertEqual(summary["conflicts"], 1)
        self.assertTrue(any(r["outcome"] == "failed" and "different content" in r["detail"] for r in rows))

    def test_global_skill_shadowing_project_skill_is_called_out(self):
        project = self.tmp / "proj"
        (project / ".agents/skills/tdd").mkdir(parents=True)
        (project / ".agents/skills/tdd/SKILL.md").write_text("project")
        self.skill(".agents/skills", "tdd", "global")
        rows, _ = skills.analyze(make_ctx(self.home, [], project=project))
        self.assertTrue(any("shadows the project skill" in r["detail"] for r in rows))

    def test_broken_symlink_and_container(self):
        (self.home / ".claude/skills").mkdir(parents=True)
        (self.home / ".claude/skills/dangling").symlink_to(self.home / "missing")
        nested = self.home / ".claude/skills/synced/uuid/morning"
        nested.mkdir(parents=True)
        (nested / "SKILL.md").write_text("m")
        rows, summary = skills.analyze(make_ctx(self.home, []))
        self.assertEqual(summary["broken"], 1)
        self.assertEqual(len(summary["containers_not_enumerated"]), 1)


def fixture_config(mode, name="codebase-memory-mcp", env=None, **kw) -> ServerConfig:
    return ServerConfig(client="claude", name=name, enabled=True, transport="stdio", provenance="test",
                        command=sys.executable, args=[str(FIXTURE), mode], env=env or {}, **kw)


class ProtocolTests(Tmp):
    def run_probe(self, cfg, ctx=None):
        ctx = ctx or make_ctx(self.home, [])
        return probe.probe_server(ctx, cfg, self.tmp / "out", python=sys.executable)

    def outcomes(self, rows):
        return {r["layer"]: r["outcome"] for r in rows}

    def test_success_through_smoke_and_body_not_retained(self):
        rows = self.run_probe(fixture_config("ok"))
        self.assertEqual(self.outcomes(rows), {"connection": "passed", "tools": "passed", "smoke": "passed"})
        diagnostic_paths = list((self.tmp / "out/diagnostics").glob("*"))
        self.assertEqual([p.suffix for p in diagnostic_paths], [".json"])
        diagnostics = json.loads(diagnostic_paths[0].read_text())
        stages = {event["stage"]: event for event in diagnostics["stages"]}
        self.assertIs(type(stages["connection"]["elapsed_ms"]), int)
        self.assertEqual((stages["discovery"]["tools_count"], stages["discovery"]["pages_count"]), (2, 1))
        self.assertEqual((diagnostics["worker_stderr"], diagnostics["server_stderr"]), ("[withheld]", "[withheld]"))
        self.assertFalse(any({"detail", "server_info", "worker_stderr", "server_stderr"} & set(event)
                             for event in diagnostics["stages"]))
        blob = json.dumps(rows) + json.dumps(diagnostics)
        self.assertNotIn("project-list-body-that-must-not-be-stored", blob)
        from ai_tools_doctor import report
        proof = report.proof_levels([{"client": "claude", "server": "codebase-memory-mcp", "enabled": True}], rows)
        self.assertEqual(proof[0]["proof"], "smoke_passed")

    def test_provider_exception_and_noisy_server_stderr_are_withheld(self):
        secret = "synthetic-provider-message-37"
        cfg = fixture_config("initialize-error", env={"FIXTURE_ERROR_TEXT": secret,
                                                         "FIXTURE_STDERR_SECRET": secret})
        rows = self.run_probe(cfg)
        diagnostics = [p.read_text() for p in (self.tmp / "out/diagnostics").glob("*")]
        blob = json.dumps(rows) + "".join(diagnostics)
        self.assertNotIn(secret, blob)
        self.assertNotIn("traceback", blob.lower())
        diag = json.loads(diagnostics[0])
        self.assertEqual((diag["worker_stderr"], diag["server_stderr"]), ("[withheld]", "[withheld]"))
        self.assertEqual(rows[0]["outcome"], "failed")
        self.assertEqual(rows[0]["reason_code"], "protocol_error")
        self.assertEqual(rows[0]["protocol_code"], -32077)

    def test_smoke_failure_does_not_retain_response_text(self):
        rows = self.run_probe(fixture_config("iserror"))
        self.assertEqual(self.outcomes(rows)["smoke"], "failed")
        smoke = next(r for r in rows if r["layer"] == "smoke")
        self.assertEqual(smoke["reason_code"], "smoke_tool_error")
        self.assertNotIn("boom", json.dumps(rows))

    def test_connection_success_is_not_a_functional_pass(self):
        rows = self.run_probe(fixture_config("ok", name="unreviewed-server"))
        self.assertEqual(self.outcomes(rows)["smoke"], "skipped")
        self.assertNotIn("smoke_passed", json.dumps(rows))

    def test_no_advertised_smoke_tool_is_unverified(self):
        self.assertEqual(self.outcomes(self.run_probe(fixture_config("no-smoke-tool")))["smoke"], "unverified")

    def test_client_restriction_blocks_smoke(self):
        cfg = fixture_config("ok", tool_restrictions={"deny": ["mcp__codebase-memory-mcp__list_projects"]})
        self.assertEqual(self.outcomes(self.run_probe(cfg))["smoke"], "unverified")

    def test_zero_tools_is_unverified_discovery(self):
        self.assertEqual(self.outcomes(self.run_probe(fixture_config("zero-tools")))["tools"], "unverified")

    def test_connection_and_discovery_share_one_20s_budget(self):
        rows = self.run_probe(fixture_config("slow-both"))
        self.assertEqual(self.outcomes(rows).get("tools") or self.outcomes(rows)["connection"], "timeout", rows)
        self.assertNotIn("smoke", self.outcomes(rows))

    def test_paginated_discovery_collects_all_pages(self):
        rows = self.run_probe(fixture_config("paginated"))
        detail = next(r["detail"] for r in rows if r["layer"] == "tools")
        self.assertIn("2 tools found across 2 page", detail)

    def test_malformed_tools_list_fails_discovery(self):
        rows = self.run_probe(fixture_config("malformed-tools"))
        self.assertEqual(self.outcomes(rows)["tools"], "failed")

    def test_is_error_result_fails_smoke(self):
        rows = self.run_probe(fixture_config("iserror"))
        self.assertEqual(self.outcomes(rows)["smoke"], "failed")
        self.assertEqual(self.outcomes(rows)["connection"], "passed")

    def test_missing_command_fails_connection(self):
        cfg = fixture_config("ok")
        cfg.command = str(self.tmp / "does-not-exist")
        row = self.run_probe(cfg)[0]
        self.assertEqual(row["outcome"], "failed")
        self.assertEqual(row["reason_code"], "executable_not_found")

    def test_http_401_and_403_are_structured_auth_failures(self):
        for status in (401, 403):
            class Handler(http.server.BaseHTTPRequestHandler):
                def do_POST(self):
                    self.send_response(status)
                    self.send_header("WWW-Authenticate", "Bearer")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                do_GET = do_POST
                def log_message(self, *a): pass
            server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            cfg = ServerConfig(client="claude", name="remote", enabled=True, transport="http", provenance="test",
                               url=f"http://127.0.0.1:{server.server_address[1]}/mcp", headers={"X-Key": "abc123456"})
            row = self.run_probe(cfg)[0]
            self.assertEqual((row["outcome"], row["reason_code"], row["http_status"]),
                             ("auth_required", f"http_{status}", status))

    def test_permission_failure_has_a_controlled_reason(self):
        command = write_exec(self.tmp / "not-executable", f"#!{sys.executable}\n")
        command.chmod(0o600)
        cfg = fixture_config("ok")
        cfg.command = str(command)
        row = self.run_probe(cfg)[0]
        self.assertEqual((row["outcome"], row["reason_code"]), ("failed", "permission_denied"))

    def test_unsupported_transport_and_oauth_and_launcher_and_empty_credential_never_start(self):
        marker = self.tmp / "started"
        base = dict(client="codex", enabled=True, provenance="test")
        cases = [
            ServerConfig(name="sse", transport="sse", url="http://x", **base),
            ServerConfig(name="oauth", transport="http", url="https://x/mcp", auth="o_auth", **base),
            ServerConfig(name="npx", transport="stdio", command="npx", args=["-y", "pkg"], **base),
            ServerConfig(name="pnpm", transport="stdio", command="pnpm", args=["dlx", "pkg"], **base),
            ServerConfig(name="github", transport="stdio", command=str(write_exec(self.tmp / "gh",
                         f"#!/bin/sh\ntouch {marker}\n")), env={"GITHUB_PERSONAL_ACCESS_TOKEN": ""},
                         unresolved=["GITHUB_PERSONAL_ACCESS_TOKEN (empty)"], **base),
        ]
        for cfg in cases:
            rows = self.run_probe(cfg)
            self.assertIn(rows[0]["outcome"], ("unverified", "skipped"), (cfg.name, rows))
        self.assertFalse(marker.exists())


class CleanupTests(Tmp):
    def test_timeout_stops_owned_tree_and_spares_sentinel(self):
        sentinel = subprocess.Popen(["sleep", "300"], start_new_session=True)
        self.addCleanup(stop_and_reap, sentinel)
        pidfile = self.tmp / "child.pid"
        cfg = fixture_config("hang-children", env={"FIXTURE_PIDFILE": str(pidfile)})
        old = probe.BACKSTOP_SECONDS
        probe.BACKSTOP_SECONDS = 4
        self.addCleanup(setattr, probe, "BACKSTOP_SECONDS", old)
        rows = probe.probe_server(make_ctx(self.home, []), cfg, self.tmp / "out", python=sys.executable)
        self.assertTrue(any(r["outcome"] == "timeout" for r in rows), rows)
        child = int(pidfile.read_text())
        time.sleep(0.5)
        self.assertFalse(alive(child), "owned grandchild survived")
        self.assertTrue(alive(sentinel.pid), "unrelated sentinel was killed")
        self.assertTrue(list((self.tmp / "out/diagnostics").glob("*.json")), "diagnostics preserved")

    def test_orphaned_grandchild_is_stopped_after_leader_exits(self):
        out = proc.run(["sh", "-c", "sleep 4177 & exit 0"], timeout=2)
        time.sleep(0.3)
        self.assertNotEqual(subprocess.run(["pgrep", "-f", "sleep 4177"], capture_output=True).returncode, 0)
        self.assertTrue(out.timed_out)

    def test_cancellation_exits_130_with_partial_report_and_clean_tree(self):
        sentinel = subprocess.Popen(["sleep", "300"], start_new_session=True)
        self.addCleanup(stop_and_reap, sentinel)
        pidfile = self.tmp / "child.pid"
        env, out = self.cli_env(f"claude={FIXTURE}:hang-children", pidfile)
        cmd = [sys.executable, "-m", "ai_tools_doctor", "--probe", "--server", "hang", "--client", "claude",
               "--kind", "mac", "--role", "personal", "--project", str(self.home), "--output-dir", str(out)]
        p = subprocess.Popen(cmd, env=env, cwd=PACKAGE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(100):
            if pidfile.exists():
                break
            time.sleep(0.1)
        self.assertTrue(pidfile.exists(), "probe never started the fixture")
        child = int(pidfile.read_text())
        p.send_signal(signal.SIGINT)
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 130)
        time.sleep(0.5)
        self.assertFalse(alive(child))
        self.assertTrue(alive(sentinel.pid))
        self.assertTrue((out / "result.json").exists())
        self.assertEqual(json.loads((out / "result.json").read_text())["state"], "cancelled")

    def test_overall_deadline_exits_124(self):
        pidfile = self.tmp / "child.pid"
        env, out = self.cli_env(f"claude={FIXTURE}:hang-children", pidfile)
        cmd = [sys.executable, "-m", "ai_tools_doctor", "--probe", "--server", "hang", "--client", "claude",
               "--kind", "mac", "--role", "personal", "--project", str(self.home), "--output-dir", str(out),
               "--deadline", "4"]
        p = subprocess.run(cmd, env=env, cwd=PACKAGE, capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 124, p.stderr)

    def cli_env(self, server_spec, pidfile):
        client, _, rest = server_spec.partition("=")
        script, _, mode = rest.rpartition(":")
        (self.home / ".claude.json").write_text(json.dumps({"mcpServers": {"hang": {
            "type": "stdio", "command": sys.executable, "args": [script, mode],
            "env": {"FIXTURE_PIDFILE": str(pidfile)}}}}))
        bins = self.tmp / "bins"
        for tool in ("claude", "codex", "opencode"):
            write_exec(bins / tool, sh() if tool != "codex" else "#!/bin/sh\n[ \"$1\" = --version ] && echo 'x 1.0.0' && exit 0\necho '[]'\n")
        env = {"HOME": str(self.home), "PATH": f"{bins}:/usr/bin:/bin:{Path(sys.executable).parent}",
               "PYTHONPATH": str(PACKAGE), "PYTHONDONTWRITEBYTECODE": "1", "FIXTURE_PIDFILE": str(pidfile)}
        return env, self.tmp / "cli-out"


class ReadOnlyAndRedactionTests(Tmp):
    def snapshot(self, root: Path):
        return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(root.rglob("*")) if p.is_file() and "ai-tools-doctor" not in str(p)}

    def setup_account(self):
        bins = self.tmp / "bins"
        marker = self.tmp / "side-effects.log"
        for tool in ("npx", "open", "xdg-open", "uv", "pip", "npm"):
            write_exec(bins / tool, f"#!/bin/sh\necho {tool} >> {marker}\n")
        codex_json = [{"name": "github", "enabled": True, "disabled_reason": None, "auth_status": "unsupported",
                       "transport": {"type": "stdio", "command": "github-mcp-server", "args": ["stdio"],
                                     "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": GH_TOKEN, "DB_PASSWORD": SHORT_SECRET},
                                     "env_vars": [], "cwd": None}},
                      {"name": "postgres", "enabled": True, "disabled_reason": None, "auth_status": "unsupported",
                       "transport": {"type": "stdio", "command": "npx", "args": ["-y", "server-postgres", PG_URL],
                                     "env": None, "env_vars": [], "cwd": None}},
                      {"name": "remote", "enabled": True, "disabled_reason": None, "auth_status": "bearer",
                       "transport": {"type": "streamable_http", "url": f"https://api.example.com/mcp?key={QUERY_SECRET}",
                                     "http_headers": {"Authorization": f"Bearer {HEADER_SECRET}"}}},
                      {"name": "codebase-memory-mcp", "enabled": True, "disabled_reason": None, "auth_status": "unsupported",
                       "transport": {"type": "stdio", "command": sys.executable,
                                     "args": [str(FIXTURE), "ok"], "env": {"FIXTURE_STDERR_SECRET": STDERR_SECRET},
                                     "env_vars": [], "cwd": None}}]
        write_exec(bins / "codex", "#!/bin/sh\nif [ \"$1\" = --version ]; then echo 'codex 0.1.0'; exit 0; fi\n"
                   f"cat <<'EOF'\n{json.dumps(codex_json)}\nEOF\n")
        write_exec(bins / "claude", sh())
        write_exec(bins / "opencode", sh())
        (self.home / ".claude.json").write_text(json.dumps({"mcpServers": {"cl": {
            "type": "stdio", "command": "tool", "args": ["--password=" + PG_PASSWORD], "env": {"K": HEADER_SECRET}}}}))
        (self.home / ".codex").mkdir()
        (self.home / ".codex/config.toml").write_text('[projects."/x"]\ntrust_level = "trusted"\n')
        return bins, marker

    def run_cli(self, bins, *extra):
        env = {"HOME": str(self.home), "PATH": f"{bins}:/usr/bin:/bin", "PYTHONPATH": str(PACKAGE),
               "PYTHONDONTWRITEBYTECODE": "1"}
        out = self.tmp / "report"
        cmd = [sys.executable, "-m", "ai_tools_doctor", "--kind", "mac", "--role", "personal",
               "--project", str(self.home), "--output-dir", str(out), *extra]
        done = subprocess.run(cmd, env=env, cwd=PACKAGE, capture_output=True, text=True, timeout=120)
        return done, out

    def assert_clean(self, done, out):
        artifacts = "".join(p.read_text() for p in out.rglob("*") if p.is_file())
        for secret in ALL_SECRETS:
            self.assertNotIn(secret, done.stdout, "leak on stdout")
            self.assertNotIn(secret, done.stderr, "leak on stderr")
            self.assertNotIn(secret, artifacts, "leak in artifacts")

    def test_inventory_leaks_nothing_and_changes_nothing(self):
        bins, marker = self.setup_account()
        before = self.snapshot(self.home)
        done, out = self.run_cli(bins)
        self.assert_clean(done, out)
        self.assertEqual(before, self.snapshot(self.home), "configuration changed")
        self.assertFalse(marker.exists(), "inventory ran an installer/browser/launcher")
        doc = json.loads((out / "result.json").read_text())
        self.assertEqual(doc["mode"], "inventory")
        github = next(s for s in doc["servers"] if s["server"] == "github" and s["client"] == "codex")
        self.assertEqual(github["env_keys"], ["DB_PASSWORD", "GITHUB_PERSONAL_ACCESS_TOKEN"])
        self.assertEqual(github["credential_values_present"], ["DB_PASSWORD", "GITHUB_PERSONAL_ACCESS_TOKEN"])
        self.assertEqual(doc["diagnostic_policy"], "structured")
        github_proof = next(p["proof"] for p in doc["proof"]
                            if (p["client"], p["server"]) == ("codex", "github"))
        self.assertEqual(github_proof, "discoverable")
        self.assertEqual(oct((out / "result.json").stat().st_mode & 0o777), "0o600")
        self.assertEqual(oct(out.stat().st_mode & 0o777), "0o700")

    def test_native_note_text_and_parser_values_are_discarded(self):
        bins, _ = self.setup_account()
        sentinel = "argument-sentinel-81"
        done, out = self.run_cli(bins, "--native-note", f"codex/github=passed:{sentinel}")
        self.assert_clean(done, out)
        self.assertNotIn(sentinel, done.stdout + done.stderr)
        doc = json.loads((out / "result.json").read_text())
        note = next(row for row in doc["results"] if row["provenance"] == "--native-note")
        self.assertEqual((note["outcome"], note["detail"], note["client"], note["server"]),
                         ("passed", "User-recorded result.", "codex", "github"))
        self.assertNotIn(sentinel, json.dumps(doc))

        table_value, table_out = self.run_cli(bins, "--native-note", "codex/github|<column>=passed:discard-me")
        self.assert_clean(table_value, table_out)
        self.assertIn("github\\|\\<column\\>", table_value.stdout)
        table_doc = json.loads((table_out / "result.json").read_text())
        table_note = next(row for row in table_doc["results"] if row["provenance"] == "--native-note")
        self.assertEqual(table_note["server"], "github|<column>")

        import shutil
        shutil.rmtree(out)
        invalid, invalid_out = self.run_cli(bins, "--native-note", f"codex/github=bad:{sentinel}")
        self.assertNotIn(sentinel, invalid.stdout + invalid.stderr)
        self.assertFalse(invalid_out.exists())
        parser_error, parser_out = self.run_cli(bins, "--client", sentinel)
        self.assertNotIn(sentinel, parser_error.stdout + parser_error.stderr)
        self.assertFalse(parser_out.exists())

        invalid_server, invalid_server_out = self.run_cli(
            bins, "--native-note", f"codex/github\n{sentinel}=passed")
        self.assertNotIn(sentinel, invalid_server.stdout + invalid_server.stderr)
        self.assertFalse(invalid_server_out.exists())

    def test_unexpected_top_level_failure_is_a_fixed_structured_error(self):
        sentinel = "top-level-failure-sentinel-52"
        stderr = io.StringIO()
        previous_umask = os.umask(0o077)
        try:
            with patch.object(cli, "_run", side_effect=RuntimeError(sentinel)), \
                    contextlib.redirect_stderr(stderr):
                code = cli.main([])
        finally:
            os.umask(previous_umask)
        self.assertEqual(code, 1)
        self.assertNotIn(sentinel, stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())
        diagnostic = json.loads(stderr.getvalue())
        self.assertEqual(diagnostic["diagnostic_policy"], "structured")
        self.assertEqual(diagnostic["results"][0]["reason_code"], "unexpected_failure")
        self.assertEqual(diagnostic["results"][0]["detail"],
                         "Doctor failed unexpectedly; internal messages and tracebacks withheld.")

    def test_malformed_client_export_becomes_fixed_unexpected_failure(self):
        bins, _ = self.setup_account()
        sentinel = "malformed-export-sentinel-64"
        write_exec(bins / "codex", "#!/bin/sh\nif [ \"$1\" = --version ]; then echo 'codex 0.1.0'; exit 0; fi\n"
                   f"printf '%s\\n' '[{{\"name\":\"broken\",\"transport\":{{\"type\":\"stdio\","
                   f"\"command\":\"server\",\"env\":\"{sentinel}\"}}}}]'\n")
        done, out = self.run_cli(bins, "--client", "codex")
        self.assertEqual(done.returncode, 1)
        self.assertNotIn(sentinel, done.stdout + done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        doc = json.loads((out / "result.json").read_text())
        row = next(row for row in doc["results"] if row["check"] == "doctor")
        self.assertEqual(row["reason_code"], "unexpected_failure")
        self.assertEqual(row["detail"], "Doctor failed unexpectedly; internal messages and tracebacks withheld.")
        self.assertNotIn(sentinel, json.dumps(doc))

    def test_malformed_opencode_entry_is_a_structured_inventory_failure(self):
        sentinel = "malformed-opencode-sentinel-82"
        bins = self.tmp / "bins"
        payloads = (f'{{"mcp":{{"broken":"{sentinel}"}}}}', '{"mcp":[]}', '{"mcp":null}')
        for payload in payloads:
            write_exec(bins / "opencode", f"#!/bin/sh\ncat <<'EOF'\n{payload}\nEOF\n")
            servers, rows = config.read_opencode(make_ctx(self.home, [bins]))
            self.assertEqual(servers, [])
            self.assertEqual((rows[0]["outcome"], rows[0]["reason_code"]),
                             ("unverified", "malformed_client_export"))
            self.assertEqual(report.exit_code(rows, None), report.EXIT_INCOMPLETE)
            self.assertNotIn(sentinel, json.dumps(rows))

    def test_probe_leaks_nothing_installs_nothing_and_skips_launchers(self):
        bins, marker = self.setup_account()
        before = self.snapshot(self.home)
        done, out = self.run_cli(bins, "--probe", "--server", "codebase-memory-mcp", "--server", "postgres",
                                 "--server", "remote", "--client", "codex")
        self.assert_clean(done, out)
        self.assertEqual(before, self.snapshot(self.home))
        self.assertFalse(marker.exists(), "probe invoked npx/open/uv/pip")
        doc = json.loads((out / "result.json").read_text())
        by = {(r["server"], r["layer"]): r["outcome"] for r in doc["results"] if r.get("server")}
        self.assertEqual(by[("codebase-memory-mcp", "smoke")], "passed")
        self.assertEqual(by[("postgres", "connection")], "skipped")
        self.assertIn(done.returncode, (1, 2))   # skipped/unverified requested targets or unrelated failures

    def test_redactor_unit(self):
        r = Redactor()
        r.add(GH_TOKEN)
        r.add_argument(PG_URL)
        r.add_url(f"https://h/x?k={QUERY_SECRET}")
        text = f"a {GH_TOKEN} b {PG_URL} c https://u:{PG_PASSWORD}@h/p?k={QUERY_SECRET} Authorization: Bearer {HEADER_SECRET}"
        cleaned = r.scrub(text)
        for secret in (GH_TOKEN, PG_PASSWORD, QUERY_SECRET, HEADER_SECRET):
            self.assertNotIn(secret, cleaned)
        self.assertEqual(r.leaks(cleaned), [])

    def test_review_regressions_redaction(self):
        r = Redactor()
        tricky = 'pa"ss\\wo\nrd-é-long'
        r.add(tricky)
        r.add("true")
        data = r.scrub_data({"server_stderr": f"boom {tricky} end", "enabled": True, "note": "true"})
        text = json.dumps(data)
        self.assertEqual(r.leaks(text), [])
        self.assertIn('"enabled": true', text)            # benign values never corrupt JSON
        self.assertEqual(r.leaks(json.dumps({"x": tricky})), [len(tricky)])   # gate sees escaped form
        flag_value = "abc" + "SECRET" + "def123"   # assembled so scanners do not flag the fixture
        r.add_arguments(["--token", flag_value])
        self.assertNotIn(flag_value, r.scrub(f"auth failed for {flag_value}"))
        r.add_url("https://mcp.example.com/s/PATHSECRET9999999/mcp#fragSecret123")
        self.assertNotIn("PATHSECRET9999999", r.scrub("404 for url https://mcp.example.com/s/PATHSECRET9999999/mcp"))
        for sample in ("sk_" + "live_abcdefgh12345678", "glpat-abcdefgh1234", "-----BEGIN PRIVATE KEY-----\nMII\n-----END PRIVATE KEY-----",
                       '"Authorization": "Basic dXNlcjpwYXNz"', "--github-token=" + "abcdef" + "123456"):
            cleaned = r.scrub(sample)
            self.assertNotIn("abcdefgh1234", cleaned)
            self.assertNotIn("dXNlcjpwYXNz", cleaned)
            self.assertNotIn("MII", cleaned)

    def test_diagnostic_escapes_and_truncation_do_not_leak(self):
        secret = "Zq" + "x" * 30 + '"\\' + "tail-end-9"
        cfg = fixture_config("ok", env={"FIXTURE_STDERR_SECRET": secret, "API_VALUE": secret})
        ctx = make_ctx(self.home, [])
        config._register(ctx, cfg)
        probe.probe_server(ctx, cfg, self.tmp / "out", python=sys.executable)
        for path in (self.tmp / "out/diagnostics").glob("*"):
            self.assertEqual(ctx.redactor.leaks(path.read_text()), [], path.name)
            self.assertNotIn("tail-end-9", path.read_text())

    def test_native_status_refuses_servers_the_probe_refused(self):
        marker = self.tmp / "claude-ran"
        write_exec(self.tmp / "bin/claude", f"#!/bin/sh\ntouch {marker}\n")
        ctx = make_ctx(self.home, [self.tmp / "bin"])
        cfg = ServerConfig(client="claude", name="github", enabled=True, transport="stdio", provenance="t",
                           command="github-mcp-server", env={"GITHUB_PERSONAL_ACCESS_TOKEN": ""},
                           unresolved=["GITHUB_PERSONAL_ACCESS_TOKEN (empty)"])
        row = probe.native_status(ctx, cfg)
        self.assertEqual(row["outcome"], "skipped")
        self.assertFalse(marker.exists())

    def test_native_status_suffix_is_not_retained(self):
        secret = "native-status-sentinel-25"
        script = write_exec(self.tmp / "bin/claude",
                            f"#!/bin/sh\nprintf '%s\\n' 'Status: Requires authentication {secret}'\nexit 37\n")
        ctx = make_ctx(self.home, [script.parent])
        cfg = ServerConfig(client="claude", name="remote", enabled=True, transport="http", provenance="test",
                           url="https://mcp.example.test/server")
        row = probe.native_status(ctx, cfg)
        self.assertEqual((row["outcome"], row["reason_code"], row["exit_code"]),
                         ("auth_required", "authentication_required", 37))
        self.assertNotIn(secret, json.dumps(row))
        self.assertEqual(row["detail"], "Claude reports that authentication is required.")

    def test_native_status_failure_keeps_exit_code_and_withholds_suffix(self):
        secret = "native-failure-sentinel-46"
        write_exec(self.tmp / "bin/claude", f"#!/bin/sh\nprintf '%s\\n' 'Status: Failed {secret}'\nexit 37\n")
        ctx = make_ctx(self.home, [self.tmp / "bin"])
        cfg = ServerConfig(client="claude", name="remote", enabled=True, transport="http", provenance="test",
                           url="https://mcp.example.test/server")
        row = probe.native_status(ctx, cfg)
        self.assertEqual((row["outcome"], row["reason_code"], row["exit_code"]),
                         ("failed", "native_status_failed", 37))
        self.assertNotIn(secret, json.dumps(row))
        self.assertEqual(row["detail"], "Claude reports a failed server status.")

    def test_empty_credential_detected_by_config_reader(self):
        cfg = ServerConfig(client="opencode", name="x", enabled=True, transport="stdio", provenance="t",
                           command="srv", env={"DATABASE_URI": "", "LOG_LEVEL": ""})
        config._flag_empty_credentials(cfg)
        self.assertEqual(cfg.unresolved, ["DATABASE_URI (empty)"])

    def test_probe_without_runtime_is_actionable_and_exit_2(self):
        bins, _ = self.setup_account()
        env = {"HOME": str(self.home), "PATH": f"{bins}:/usr/bin:/bin", "PYTHONPATH": str(PACKAGE)}
        python = str(Path(sys.base_prefix) / f"bin/python{sys.version_info.major}.{sys.version_info.minor}")
        if not Path(python).is_file():
            self.skipTest("base Python executable is unavailable")
        done = subprocess.run([python, "-m", "ai_tools_doctor", "--kind", "mac", "--probe", "--server",
                               "x", "--project", str(self.home), "--output-dir", str(self.tmp / "o")],
                              env=env, cwd=PACKAGE, capture_output=True, text=True)
        if python == sys.executable or "No module named" in done.stderr:
            self.skipTest("python3 on PATH is the test interpreter or lacks the stdlib needed")
        self.assertIn(done.returncode, (1, 2), done.stderr)   # 1 wins when fixture ownership also fails
        self.assertTrue((self.tmp / "o/result.json").exists(), done.stdout + done.stderr)
        row = next(r for r in json.loads((self.tmp / "o/result.json").read_text())["results"]
                   if r["check"] == "probe runtime")
        self.assertEqual((row["outcome"], row["next_action"]), ("unverified", "Run: ai-tools-doctor setup"))


if __name__ == "__main__":
    unittest.main()
