"""Owned subprocess execution: one session per child, bounded, descendants-only cleanup."""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass, field

_OWNED: dict[int, subprocess.Popen] = {}


class Cancelled(Exception):
    """Raised when the doctor is cancelled (SIGINT/SIGTERM) or hits its overall deadline."""


@dataclass
class Outcome:
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    lines: list[str] = field(default_factory=list)
    timed_out: bool = False
    spawn_error: str | None = None


def _snapshot() -> dict[int, tuple[int, int]]:
    """pid -> (ppid, pgid) for every process. Used only to walk our own subtree."""
    try:
        out = subprocess.run(["ps", "-axo", "pid=,ppid=,pgid="], capture_output=True, text=True, timeout=5).stdout
    except subprocess.TimeoutExpired:
        return {}
    table = {}
    for row in out.splitlines():
        parts = row.split()
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            table[int(parts[0])] = (int(parts[1]), int(parts[2]))
    return table


def descendants(root: int) -> set[int]:
    table = _snapshot()
    found, frontier = set(), {root}
    while frontier:
        frontier = {pid for pid, (ppid, _) in table.items() if ppid in frontier and pid not in found}
        found |= frontier
    return found


_CLEANING = False
_PENDING: list[str] = []   # signal received during cleanup; raised afterwards


def _group_has_members(pgid: int) -> bool:
    return any(g == pgid for _, g in _snapshot().values())


def _signal_group(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def terminate_tree(proc: subprocess.Popen, grace: float = 1.5) -> None:
    """Stop the child's own session/group and every descendant found by parent links.

    The child leads a session we created (start_new_session), so its group id is ours.
    Descendants that moved to other sessions are found by walking parent pids and are
    re-discovered before each signalling round.
    """
    global _CLEANING
    _CLEANING = True   # a second signal or the deadline must not interrupt cleanup
    try:
        own_group = os.getpgrp()
        known: dict[int, int] = {}
        for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 1.0)):
            fresh = descendants(proc.pid)
            for pid in fresh:
                try:
                    known[pid] = os.getpgid(pid)
                except ProcessLookupError:
                    pass
            # Earlier-seen pids are signalled again only while still in the process group first seen,
            # so a recycled pid is never hit.
            tree = set(fresh)
            for pid, pgid0 in known.items():
                try:
                    if pid not in fresh and os.getpgid(pid) == pgid0:
                        tree.add(pid)
                except ProcessLookupError:
                    pass
            tree -= {os.getpid()}
            groups = set()
            for pid in tree:
                try:
                    pgid = os.getpgid(pid)
                except ProcessLookupError:
                    continue
                if pgid in tree and pgid != own_group:   # group leader is inside the owned tree
                    groups.add(pgid)
            if proc.pid != own_group and (proc.returncode is None or _group_has_members(proc.pid)):
                groups.add(proc.pid)   # our own session, even if its leader already exited
            for group in groups:
                _signal_group(group, sig)
            for pid in tree:
                try:
                    os.kill(pid, sig)
                except (ProcessLookupError, PermissionError):
                    pass
            end = time.monotonic() + wait
            while time.monotonic() < end:
                proc.poll()
                if not _live_pids(tree):
                    break
                time.sleep(0.1)
            if proc.poll() is not None and not _live_pids(tree):
                break
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
    finally:
        _CLEANING = False
    if _PENDING:
        raise Cancelled(_PENDING.pop())


def _live_pids(pids) -> set[int]:
    """One bounded ps call for all pids; zombies do not count (reaping is left to Popen.poll)."""
    if not pids:
        return set()
    try:
        out = subprocess.run(["ps", "-o", "pid=,stat=", "-p", ",".join(map(str, pids))],
                             capture_output=True, text=True, timeout=5).stdout
    except subprocess.TimeoutExpired:
        return set(pids)
    return {int(r.split()[0]) for r in out.splitlines() if len(r.split()) == 2 and not r.split()[1].startswith("Z")}


def kill_owned() -> None:
    for proc in list(_OWNED.values()):
        terminate_tree(proc)
    _OWNED.clear()


def run(args: list[str], *, timeout: float, env: dict[str, str] | None = None, cwd: str | None = None,
        stdin: str | None = None, on_line=None) -> Outcome:
    """Run args in a new session. Enforce the deadline; stream stdout lines to on_line."""
    try:
        proc = subprocess.Popen(
            args, env=env, cwd=cwd, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    except OSError as exc:
        return Outcome(None, spawn_error=f"{type(exc).__name__}: {exc.strerror or exc}")
    _OWNED[proc.pid] = proc
    result = Outcome(None)
    try:
        if stdin is not None:
            try:
                proc.stdin.write(stdin.encode())
                proc.stdin.close()
            except BrokenPipeError:
                pass
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ, "out")
        selector.register(proc.stderr, selectors.EVENT_READ, "err")
        buffers = {"out": b"", "err": b"", "out_all": b""}
        deadline = time.monotonic() + timeout
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                result.timed_out = True
                break
            for key, _ in selector.select(min(remaining, 0.25)):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffers[key.data] += chunk
                if key.data == "out":
                    buffers["out_all"] += chunk
                    buffers["out"] += chunk
                    while b"\n" in buffers["out"]:
                        line, _, buffers["out"] = buffers["out"].partition(b"\n")
                        result.lines.append(line.decode(errors="replace"))
                        if on_line:
                            on_line(result.lines[-1])
        if result.timed_out:
            terminate_tree(proc)
        else:
            try:
                # Wait for exit WITHOUT reaping, so the group id cannot be recycled before we clean it.
                end = time.monotonic() + max(0.1, deadline - time.monotonic())
                while time.monotonic() < end:
                    try:
                        if os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT):
                            break
                    except ChildProcessError:
                        break
                    time.sleep(0.02)
                else:
                    raise subprocess.TimeoutExpired(args, 0)
                _signal_group(proc.pid, signal.SIGKILL)   # nothing may outlive its probe in our session
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                result.timed_out = True
                terminate_tree(proc)
        result.returncode = proc.returncode
        result.stdout = buffers["out_all"].decode(errors="replace")
        result.stderr = buffers["err"].decode(errors="replace")
        return result
    except BaseException:
        terminate_tree(proc)
        raise
    finally:
        _OWNED.pop(proc.pid, None)
        for stream in (proc.stdout, proc.stderr):
            try:
                stream.close()
            except Exception:
                pass


def install_cancellation(deadline_seconds: float | None) -> None:
    """Turn SIGINT/SIGTERM/SIGALRM into Cancelled so owned children are cleaned up by `run`."""
    def cancel(signum, _frame):
        if _CLEANING:
            _PENDING.append("deadline" if signum == signal.SIGALRM else "cancelled")
            return
        raise Cancelled("deadline" if signum == signal.SIGALRM else "cancelled")
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGALRM, signal.SIGHUP, signal.SIGQUIT):
        signal.signal(sig, cancel)
    if deadline_seconds:
        signal.setitimer(signal.ITIMER_REAL, deadline_seconds)
