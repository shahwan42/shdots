#!/usr/bin/env python3
"""Checks that the shell guard hook blocks the failing forms and allows the working ones."""
import json
from pathlib import Path
import subprocess

HOOK = Path(__file__).resolve().parents[1] / 'dot_local/bin/executable_shell-guard-hook'

BLOCKED = [
    "sed -i 's/a/b/' file",
    "cd x && sed -i -e 's/a/b/' file",
    "rg foo | sed -i 's/a/b/' f",
    "sed -i -e 's/a/b/' file",
    "git rev-parse --short origin/main HEAD",
    "git fetch -q && git rev-parse --verify a b",
    "php artisan test --parallel --compact",
    "cd repo && /opt/homebrew/opt/php@8.4/bin/php artisan test --parallel --processes=14",
    "(cd repo && APP_ENV=testing php artisan test --parallel)",
    "vendor/bin/sail artisan test --parallel",
    "vendor/bin/pest --parallel",
    "php vendor/bin/paratest --processes=14 > log 2>&1",
    "php scripts/tests",
    "cd repo && APP_ENV=testing /opt/homebrew/opt/php@8.4/bin/php scripts/tests > log 2>&1",
    "./scripts/tests all",
    "vendor/bin/sail php scripts/tests",
    "sh scripts/pre-push </dev/null",
    "php scripts/phpunit",
    "cd ~/Code/foodics/pay/pay && CI_NODE_INDEX=2 php scripts/phpunit > log 2>&1",
    "scripts/ci-local --base origin/main",
    "cd ~/Code/worktrees/farm_management_system/x && pnpm ci:local --base origin/main",
    "cd ~/Code/worktrees/farm_management_system/x && mise exec -- pnpm run test:e2e",
    "cd ~/Code/worktrees/farm_management_system/x; pnpm test",
    "cd ~/Code/worktrees/capital-api/x && git push -u origin x",
    "GIT_SSH_COMMAND='ssh -o ServerAliveInterval=20' git -C ~/Code/foodics/capital/capital-api push",
]
ALLOWED = [
    "sed -i '' 's/a/b/' file",
    'sed -i "" "s/a/b/" file',
    "sed -n '1,5p' file",
    "sed 's/a/b/' file > out",
    "git rev-parse --short HEAD",
    "git rev-parse origin/main HEAD",
    "git rev-parse --show-toplevel",
    "ls -i file",
    "git commit -m 'avoid sed -i x on macOS'",
    "echo 'sed -i s/a/b/ f' > note.txt",
    "heavy run -- php artisan test --parallel --compact",
    "cd repo && ~/.local/bin/heavy run --label suite -- vendor/bin/pest --parallel",
    "php artisan test --compact tests/Feature/FooTest.php",
    "vendor/bin/pest --filter=testName",
    "heavy run -- php scripts/tests",
    "php scripts/tests arch",
    "php scripts/tests shard",
    "rg -n processes scripts/tests",
    "git add scripts/tests scripts/pre-push",
    "cat scripts/pre-push",
    "cd ~/Code/worktrees/capital-api/x && heavy run -- git push -u origin x",
    "cd ~/Code/worktrees/capital-api/x && git push --dry-run origin x",
    "cd ~/Code/worktrees/capital-api/x && git status && git log --oneline -3",
    "cd ~/Code/worktrees/chezmoi/x && git push -u origin x",
    "slot test cp-api --parallel phpunit",
    "git commit -m 'stop running artisan test --parallel twice'",
    "rg -n 'artisan test --parallel' scripts",
    'rg -n "phpunit|artisan test|--parallel|paratest" scripts/pre-push | head -20',
    "rg -n paratest scripts/phpunit scripts/tests",
    "echo done; cat scripts/phpunit | head",
    "php scripts/phpunit --plan",
    "scripts/ci-local --stop",
    "cd ~/Code/worktrees/farm_management_system/x && heavy run -- pnpm ci:local --base origin/main",
    "cd ~/Code/worktrees/farm_management_system/x && pnpm --filter api test",
    "cd ~/Code/worktrees/farm_management_system/x && pnpm test apps/api/src/one.test.ts",
    "cd ~/Code/worktrees/farm_management_system/x && pnpm lint && pnpm typecheck",
    "cd ~/Code/worktrees/farm_management_system/x && git push -u origin x",
    "cd ~/Code/worktrees/capital-console/x && pnpm test",
    "cd ~/Code/foodics/pay/pay && git push -u origin x",
]


def run(command, tool='Bash', cwd='/tmp'):
    event = {'tool_name': tool, 'tool_input': {'command': command}, 'cwd': cwd}
    return subprocess.run(['python3', str(HOOK)], input=json.dumps(event),
                          text=True, capture_output=True)


for command in BLOCKED:
    result = run(command)
    assert result.returncode == 2 and result.stderr.startswith('Blocked:'), (command, result)
for command in ALLOWED:
    result = run(command)
    assert result.returncode == 0 and not result.stderr, (command, result)
assert run("sed -i 's/a/b/' f", tool='Read').returncode == 0
# A push is judged by where it runs: only a repository whose pre-push hook runs the suite.
assert run('git push', cwd='/Users/x/Code/foodics/capital/capital-api').returncode == 2
assert run('heavy run -- git push', cwd='/Users/x/Code/foodics/capital/capital-api').returncode == 0
assert run('git push', cwd='/Users/x/Code/foodics/capital/capital-admin').returncode == 0
# A `cd` or `git -C` to another repository wins over the folder the session started in.
assert run('cd ~/Code/worktrees/chezmoi/x && git push', cwd='/Users/x/Code/foodics/capital/capital-api').returncode == 0
assert run('git -C ~/Code/worktrees/chezmoi/x push', cwd='/Users/x/Code/foodics/capital/capital-api').returncode == 0
assert run('cd ~/Code/worktrees/capital-api/x && git push', cwd='/Users/x/Code/chezmoi').returncode == 2
# A package script is judged the same way: only where it runs the whole suite.
assert run('pnpm test', cwd='/Users/x/Code/side-hustle/fms/repos/farm_management_system').returncode == 2
assert run('pnpm test', cwd='/Users/x/Code/foodics/capital/capital-console').returncode == 0
bad = subprocess.run(['python3', str(HOOK)], input='not json', text=True, capture_output=True)
assert bad.returncode == 0
print('shell guard hook ok')
