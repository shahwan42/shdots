"""Scratch-only checks for stop-worktree-procs (worktrunk's pre-remove hook).

Stages processes in a throwaway "worktree", deletes it, runs the source script
and checks what was stopped and what was left alone. Only processes this test
started are ever targeted: the path is a fresh temp directory.
"""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from platform_stabilization import check

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'dot_local/bin/executable_stop-worktree-procs'

tmp = Path(tempfile.mkdtemp(prefix='shdots-stopprocs-'))
wt = tmp/'worktrees'/'repo'/'branch'
outside = tmp/'elsewhere'
for d in (wt, outside):
    d.mkdir(parents=True)
PY = sys.executable
started = []


def spawn(args, cwd, **kw):
    p = subprocess.Popen(args, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, **kw)
    started.append(p)
    return p


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # a reaped-later child of this test shows as a zombie until waited on
    out = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True).stdout
    return bool(out.strip()) and not out.strip().startswith('Z')


def child_of(pid):
    out = subprocess.run(['pgrep', '-P', str(pid)], capture_output=True, text=True).stdout.split()
    return [int(x) for x in out]


def run(*args):
    return subprocess.run([PY, str(SCRIPT), *args], capture_output=True, text=True)


try:
    # a detached dev server whose child moved elsewhere: stopped as a whole group
    server = spawn([PY, '-c', 'import subprocess,time; subprocess.Popen(["sleep","600"], cwd="%s"); time.sleep(600)'
                    % outside], wt, start_new_session=True)
    # ignores SIGTERM: needs the SIGKILL after the grace period
    stubborn = spawn([PY, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(600)'],
                     wt, start_new_session=True)
    # a fake agent session: argv[0] "claude" (bash keeps it; macOS's python3 stub re-execs and
    # loses it); it owns an MCP-like child and a shell tool call
    inner = '%s -c "import time; time.sleep(600)" & sh -c "sleep 600; true" & wait' % PY
    agent = spawn(['bash', '-c', 'exec -a claude bash -c "$0"', inner], wt, start_new_session=True)
    # on a terminal (script gives sleep a pty): never stopped
    term = spawn(['script', '-q', '/dev/null', 'sleep', '600'], wt, start_new_session=True)
    # not in the worktree: never touched
    control = spawn(['sleep', '600'], outside, start_new_session=True)
    deadline = time.time() + 10
    while time.time() < deadline and not (child_of(server.pid) and len(child_of(agent.pid)) == 2
                                         and child_of(term.pid)):
        time.sleep(0.1)
    server_child = child_of(server.pid)[0]
    mcp, tool = sorted(child_of(agent.pid), key=lambda p: 'sh -c' in subprocess.run(
        ['ps', '-o', 'args=', '-p', str(p)], capture_output=True, text=True).stdout)
    tty_sleep = child_of(term.pid)[0]

    shutil.rmtree(wt)  # the hardest case: matching works even once the directory is gone

    result = run('--dry-run', str(wt))
    check(result.returncode == 0 and 'would stop' in result.stdout, f'dry run: {result.stdout}{result.stderr}')
    check(alive(server.pid) and alive(stubborn.pid), 'dry run stopped something')
    print('PASS: --dry-run reports without signalling')

    for broad in (os.path.expanduser('~'), os.path.expanduser('~/Code'), '/Users'):
        check(run('--dry-run', broad).stdout.startswith('stop-worktree-procs: refusing'), f'{broad} not refused')
    print('PASS: home, ~/Code and shallow paths are refused')

    result = run('--grace', '1', str(wt))
    check(result.returncode == 0, f'exit {result.returncode}: {result.stderr}')
    for p in started:
        try:
            p.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            pass
    stopped = {'server': server.pid, 'server child elsewhere': server_child, 'SIGTERM-ignoring': stubborn.pid,
               'agent shell tool call': tool}
    kept = {'agent session': agent.pid, 'agent-owned MCP child': mcp, 'terminal process': tty_sleep,
            'outside control': control.pid}
    for name, pid in stopped.items():
        check(not alive(pid), f'{name} ({pid}) still running\n{result.stdout}')
    for name, pid in kept.items():
        check(alive(pid), f'{name} ({pid}) was stopped\n{result.stdout}')
    check('left running %d (agent session)' % agent.pid in result.stdout, f'agent not listed:\n{result.stdout}')
    check('left running %d (on a terminal)' % tty_sleep in result.stdout, f'terminal not listed:\n{result.stdout}')
    print('PASS: worktree processes stopped; agent, its MCP child, terminal and outside processes kept')
finally:
    # every spawn leads its own group (start_new_session); script's pty child has its own session
    for p in started:
        kids = child_of(p.pid)
        for kill, target in [(os.killpg, p.pid)] + [(os.kill, c) for c in kids]:
            try:
                kill(target, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
    shutil.rmtree(tmp, ignore_errors=True)
