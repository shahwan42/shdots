#!/usr/bin/env python3
"""Checks that heavy queues commands, passes exit codes through, and frees a slot when its holder dies."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

HEAVY = Path(__file__).resolve().parents[1] / 'dot_local/bin/executable_heavy'

state = tempfile.mkdtemp(prefix='heavy-test-')
BASE_ENV = {k: v for k, v in os.environ.items() if not k.startswith('HEAVY_')}
BASE_ENV.update(HEAVY_STATE_DIR=state, HEAVY_NICE='0')


def heavy(*args, **env):
    return subprocess.run([sys.executable, str(HEAVY), *args], env=dict(BASE_ENV, **env),
                          text=True, capture_output=True)


def start(*args, **env):
    return subprocess.Popen([sys.executable, str(HEAVY), *args], env=dict(BASE_ENV, **env),
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def wait_until_held():
    for _ in range(100):
        if 'slot 1: free' not in heavy('status').stdout:
            return
        time.sleep(0.05)
    raise AssertionError('the slot was never taken')


# The command's exit code and output come back unchanged.
result = heavy('run', '--', 'sh', '-c', 'echo out; exit 7')
assert result.returncode == 7 and result.stdout == 'out\n', result

# The command is told it holds a slot and how many workers it may start.
result = heavy('run', '--', 'sh', '-c', 'echo $HEAVY_HELD $HEAVY_PROCS', HEAVY_PROCS='6')
assert result.stdout == '1 6\n', result

# A missing command reports 127 and leaves the slot free.
result = heavy('run', '--', 'no-such-command-here')
assert result.returncode == 127, result
assert 'slot 1: free' in heavy('status').stdout

# While one command holds the only slot, a second gives up with 75 and runs nothing.
marker = Path(state) / 'ran'
first = start('run', '--label', 'first job', '--', 'sleep', '3137')
wait_until_held()
status = heavy('status').stdout
assert 'first job' in status and '1 of 1 slot(s) in use; 0 waiting' in status, status
second = heavy('run', '--wait', '1', '--', 'touch', str(marker))
assert second.returncode == 75 and not marker.exists(), second
assert 'first job' in second.stderr, second

# A run started inside another run goes straight through instead of waiting on itself.
nested = heavy('run', '--wait', '1', '--', 'sh', '-c', 'echo nested', HEAVY_HELD='1')
assert nested.returncode == 0 and nested.stdout == 'nested\n', nested

# With two slots the second command runs alongside the first.
both = heavy('run', '--wait', '1', '--', 'sh', '-c', 'echo second', HEAVY_SLOTS='2')
assert both.returncode == 0 and both.stdout == 'second\n', both

# Waiting commands start in the order they arrived, once the holder is killed, even with
# SIGKILL. A waiter that dies in line does not hold up the ones behind it.
order = Path(state) / 'order'
def queued(name):
    waiter = start('run', '--wait', '30', '--', 'sh', '-c', f'echo {name} >> {order}; sleep 0.2')
    time.sleep(0.7)
    return waiter
dead = queued('dead')
waiters = [queued(name) for name in ('one', 'two', 'three')]
assert '4 ahead in line' in heavy('run', '--wait', '1', '--', 'true').stderr
assert '4 waiting' in heavy('status').stdout, heavy('status').stdout
dead.send_signal(signal.SIGKILL)
dead.wait()
began = time.monotonic()
first.send_signal(signal.SIGKILL)
first.wait()
for waiter in waiters:
    assert waiter.wait(timeout=10) == 0
assert order.read_text() == 'one\ntwo\nthree\n', order.read_text()
assert time.monotonic() - began < 8
assert '0 waiting' in heavy('status').stdout

# The worker count is there for callers that build a command before they hold a slot.
assert heavy('procs', HEAVY_PROCS='6').stdout == '6\n'
subprocess.run(['pkill', '-f', 'sleep 3137'], check=False)  # the killed holder's orphan

# A stop request reaches the command, and its signal becomes the exit code.
stopped = start('run', '--', 'sleep', '30')
wait_until_held()
stopped.send_signal(signal.SIGTERM)
assert stopped.wait(timeout=5) == 128 + signal.SIGTERM, stopped.returncode
assert 'slot 1: free' in heavy('status').stdout

# Every run leaves one log line, and the report sums them up per project.
import json
log = [json.loads(line) for line in (Path(state) / 'log.jsonl').read_text().splitlines()]
outcomes = [event['outcome'] for event in log]
assert outcomes.count('gave_up') == 2 and 'not_started' in outcomes, outcomes
assert all({'at', 'label', 'cwd', 'waited', 'ahead', 'load_arrived'} <= set(event) for event in log), log
three = next(event for event in log if 'echo three' in event['label'])
assert three['outcome'] == 'ran' and three['exit'] == 0 and three['waited'] >= 1 and three['ahead'] == 3, three
assert next(event for event in log if event.get('exit') == 143)
text = heavy('report').stdout
assert f'{len(log)} runs' in text and '2 gave up' in text and 'by project:' in text, text
assert 'no runs logged' in heavy('report', HEAVY_STATE_DIR=tempfile.mkdtemp(prefix='heavy-empty-')).stdout

print('heavy: ok')
