#!/usr/bin/env python3
"""Account-boundary regression checks. Only scratch state is written; no installers run."""
import ast
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
from platform_stabilization import verify_profile, verify_bootstrap

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = Path(os.environ.get('SHDOTS_AUDIT_DIR', tempfile.mkdtemp(prefix='shdots-account-audit-')))
ARTIFACTS.mkdir(parents=True, exist_ok=True)


def run(args, input=None, check=True):
    result = subprocess.run(args, input=input, text=True, capture_output=True)
    if check and result.returncode:
        raise AssertionError(f"Command failed ({result.returncode}): {args}\n{result.stdout}{result.stderr}")
    return result


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def profile(label, username, role, kind='mac', extra=None):
    audit = ARTIFACTS / label
    audit.mkdir(exist_ok=True)
    dest = audit / 'empty-home'
    dest.mkdir(exist_ok=True)
    data = dict(kind=kind, hostname='as-host' if kind == 'mac' else 'fdx-dev', role=role,
                eod=False, auto_update=False, secret_integrations=(role == 'personal'), git_signing=False)
    data.update(extra or {})
    config = audit / 'chezmoi.toml'
    config.write_text('[data]\n' + '\n'.join(f'{k} = {json.dumps(v)}' for k, v in data.items()) + '\n')
    account_home = ('/Users/' if kind == 'mac' else '/home/') + username
    override = {'chezmoi': {'username': username, 'homeDir': account_home,
                            'sourceDir': account_home + '/.local/share/chezmoi', 'os': 'darwin' if kind == 'mac' else 'linux'}}
    base = ['chezmoi', '--config', str(config), '--source', str(ROOT), '--destination', str(dest),
            '--cache', str(audit/'cache'), '--persistent-state', str(audit/'state.boltdb'),
            '--refresh-externals=never', '--no-tty', '--no-pager', '--color=false',
            '--override-data', json.dumps(override)]
    command_log = []

    def cz(*args, input=None, check=True):
        actual_args = list(args)
        actual_base = list(base)
        # CLI override flags replace, rather than merge, earlier overrides.
        # Merge here so every negative/opt-in case keeps the simulated OS identity.
        if '--override-data' in actual_args:
            index = actual_args.index('--override-data')
            changed = json.loads(actual_args[index + 1])
            merged = json.loads(json.dumps(override))
            for key, value in changed.items():
                if key == 'chezmoi':
                    merged['chezmoi'].update(value)
                else:
                    merged[key] = value
            actual_base[-1] = json.dumps(merged)
            del actual_args[index:index + 2]
        command_log.append(actual_base + actual_args)
        return run(actual_base + actual_args, input, check)

    # Render init independently of the existing as config; this also verifies defaults.
    init = cz('execute-template', '--init', '--file', str(ROOT/'.chezmoi.toml.tmpl')).stdout
    (audit/'init.toml').write_text(init)
    init_json = json.loads(cz('execute-template', '--with-stdin', '{{ .chezmoi.stdin | fromToml | toJson }}', input=init).stdout)
    check(init_json['data']['role'] == role, f'{label}: incorrect init role')
    check(init_json['data']['username'] == username, f'{label}: incorrect init username')
    if kind == 'mac':
        check('age' not in init_json and 'encryption' not in init_json, f'{label}: native age configuration')
        # Omit saved onboarding flags so these assertions exercise template defaults.
        defaults_config = audit / 'defaults.toml'
        defaults_config.write_text('[data]\n' + '\n'.join(
            f'{k} = {json.dumps(data[k])}' for k in ('kind', 'hostname', 'role')) + '\n')
        defaults_base = list(base)
        defaults_base[2] = str(defaults_config)
        defaults_args = defaults_base + ['execute-template', '--init', '--file', str(ROOT/'.chezmoi.toml.tmpl')]
        command_log.append(defaults_args)
        defaults = run(defaults_args).stdout
        (audit/'defaults-init.toml').write_text(defaults)
        defaults_json = json.loads(cz('execute-template', '--with-stdin', '{{ .chezmoi.stdin | fromToml | toJson }}', input=defaults).stdout)
        check(defaults_json['data']['auto_update'] is False, f'{label}: automatic updates default enabled')
        check(defaults_json['data']['eod'] is False, f'{label}: EOD default enabled')
        if role == 'work':
            check(defaults_json['data']['secret_integrations'] is False, f'{label}: secret integrations default enabled')
            check(defaults_json['data']['git_signing'] is False, f'{label}: signing requires unprovisioned key')
    # Metadata-only listing proves ignore gates, without masking them by exclusion.
    encrypted = cz('managed', '--include=encrypted', '--format=json').stdout.splitlines()
    (audit/'encrypted-targets.json').write_text(json.dumps(encrypted, indent=2) + '\n')
    if kind == 'mac':
        check(encrypted == [], f'{label}: native encrypted targets are still eligible')
    # No encrypted consumer is requested, including for compatibility renders.
    dump = cz('dump', '--exclude=encrypted,externals', '--format=json')
    (audit/'dump.json').write_text(dump.stdout)
    entries = json.loads(dump.stdout)
    (audit/'managed.json').write_text(cz('managed', '--exclude=encrypted,externals', '--format=json').stdout)
    rendered = audit/'rendered'
    rendered.mkdir(exist_ok=True)
    all_text = ''
    counts = {'file': 0, 'script': 0, 'symlink': 0, 'dir': 0, 'remove': 0}
    for name, entry in entries.items():
        counts[entry['type']] = counts.get(entry['type'], 0) + 1
        contents = entry.get('contents', '')
        all_text += contents + '\n' + entry.get('target', '')
        if contents:
            target = rendered/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents)
            if name.endswith('.json') or name.endswith('.jsonc'):
                json.loads(contents)
            if name.endswith('.toml'):
                cz('execute-template', '--with-stdin', '{{ .chezmoi.stdin | fromToml | toJson }}', input=contents)
            if name.endswith('.plist'):
                plistlib.loads(contents.encode())
            if entry['type'] == 'script' or contents.startswith('#!/bin/sh'):
                run(['sh', '-n', str(target)])
            elif contents.startswith('#!/bin/bash'):
                run(['bash', '-n', str(target)])
            elif contents.startswith('#!/bin/zsh') or name in ('.zshrc', '.zshenv', '.zprofile') or name.endswith('.zsh'):
                run(['zsh', '-n', str(target)])
            if "<<'PY'" in contents:
                ast.parse(contents.split("<<'PY'", 1)[1].split('\nPY', 1)[0])
    gitconfig = entries['.gitconfig']['contents']
    gitfile = rendered/'.gitconfig'
    email = run(['git', 'config', '--file', str(gitfile), 'user.email']).stdout.strip()
    expected = 'a.shahwan@foodics.com' if role == 'work' else 'a.shahwan42@gmail.com'
    check(email == expected, f'{label}: incorrect Git email {email}')
    full_name = run(['git', 'config', '--file', str(gitfile), 'user.name']).stdout.strip()
    expected_name = 'A. S. Foodics' if role == 'work' else 'Ahmed Shahwan'
    check(full_name == expected_name, f'{label}: incorrect Git full name {full_name}')
    check('includeIf' not in gitconfig, f'{label}: path-dependent identity remains')
    if kind == 'mac':
        check(not any(e['type'] == 'remove' for e in entries.values()), f'{label}: native state deletion')
        check('.config/op/env' not in entries and '.ssh/config.d/foodics' not in entries, f'{label}: legacy encrypted target')
        check('Library/LaunchAgents/com.shahwan42.chezmoi-update.plist' not in entries, f'{label}: update agent active')
        check('launchctl bootstrap' not in entries['30-schedule-autoupdate.sh']['contents'], f'{label}: scheduling active')
        updater = entries['.local/bin/chezmoi-autoupdate']['contents']
        check(updater.index('exit 0') < updater.index('fetch -q origin'), f'{label}: disabled updater can fetch')
        check(not any('/tasks/' in name or name.endswith(('.timer', '.service')) for name in entries), f'{label}: scheduled task deployed')
        check('sail=' not in entries['.zshrc']['contents'], f'{label}: Docker alias is default')
        check(all('as-dev' not in e.get('contents', '') for n, e in entries.items() if n != '.config/git/allowed_signers'), f'{label}: old VM default/reference in native render')
        check('command herdr --remote' not in entries['.zshrc']['contents'], f'{label}: remote startup')
        check('.claude/skills/eod/SKILL.md' not in entries, f'{label}: EOD default enabled')
        check('~/Code/worktrees/{{ repo }}/{{ branch | sanitize_hash }}' in entries['.config/worktrunk/config.toml']['contents'], f'{label}: wrong worktree path')
        keyboard = json.loads(entries['.config/karabiner/assets/complex_modifications/native-account-baseline.json']['contents'])
        mappings = keyboard['rules'][0]['manipulators']
        check(len(mappings) == 2 and all(m['type'] == 'basic' for m in mappings), f'{label}: invalid keyboard candidate structure')
        check([(m['from']['key_code'], m['to'][0]['key_code']) for m in mappings] == [('caps_lock', 'escape'), ('escape', 'caps_lock')], f'{label}: incorrect keyboard candidate')
        check('.config/karabiner/karabiner.json' not in entries, f'{label}: keyboard candidate activated')
        verify_profile(label, entries, rendered, audit, cz)
        run(['/usr/bin/ssh', '-G', '-F', str(rendered/'.ssh/config'), 'github.foodics.com' if role == 'work' else 'github.com'])
        # Full non-mutating diff and apply against empty scratch destination.
        before = sorted(str(f.relative_to(dest)) for f in dest.rglob('*'))
        diff = cz('diff', '--exclude=encrypted,externals')
        (audit/'diff.txt').write_text(diff.stdout)
        dry = cz('apply', '--dry-run', '--verbose', '--exclude=encrypted,externals')
        (audit/'dry-run.txt').write_text(dry.stdout + dry.stderr)
        after = sorted(str(f.relative_to(dest)) for f in dest.rglob('*'))
        check(before == after == [], f'{label}: dry run changed destination')
    if kind == 'mac' and role == 'work':
        for needle in ['/Users/as', 'a.shahwan42@gmail.com', 'ahmed@shahwan.me', 'xwug424pq6bcit35v5abzpt5vm', 'jypxoxjttljurjhg3f72bvlx6e', 'postgresql://tutoring', 'OP_SERVICE_ACCOUNT_TOKEN']:
            check(needle not in all_text, f'{label}: personal leakage: {needle}')
        check('.config/zsh/secrets.zsh' not in entries, f'{label}: unprovisioned secret consumer')
        check('.local/bin/mcp-github-register' not in entries, f'{label}: unprovisioned MCP token helper')
        check('.claude/skills/qa-manual/SKILL.md' not in entries, f'{label}: personal project skill')
        check('.ssh/authorized_keys' not in entries, f'{label}: legacy host access grant')
        check('.ssh/config.d/personal/shahwan' not in entries, f'{label}: personal Hetzner host')
        check('export GH_HOST=github.foodics.com' in entries['.zshenv']['contents'], f'{label}: Enterprise CLI default missing')
        check('brew bundle' not in entries['25-brew-bundle.sh']['contents'], f'{label}: Homebrew mutation')
        check('op_read \'op://' not in entries['40-claude-mcp-sync.sh']['contents'] + entries['43-codex-mcp-sync.sh']['contents'], f'{label}: automatic PAT acquisition')
        check('"enabled": False' in entries['41-opencode-mcp-sync.sh']['contents'], f'{label}: unprovisioned GHE enabled')
    if kind == 'mac' and role == 'personal':
        for needle in ['i4fkk5sxnoihinvcnv2evqg7be', 'cuhmbyox773pricvf6xmm5nfba', 'vxwnzlffnicehkjjd5jjmg63xe']:
            check(needle not in all_text, f'{label}: work token consumer')
        check('servers["gmail"]' in entries['41-opencode-mcp-sync.sh']['contents'], f'{label}: personal Gmail missing')
        check('.claude/skills/qa-manual/SKILL.md' in entries, f'{label}: personal QA missing')
        check('.ssh/config.d/personal/shahwan' in entries, f'{label}: Hetzner host missing')
    (audit/'commands.json').write_text(json.dumps(command_log, indent=2) + '\n')
    (audit/'summary.json').write_text(json.dumps(dict(label=label, username=username, role=role, kind=kind, counts=counts, git_name=full_name, git_email=email, externals='excluded (no downloads)', encrypted='excluded (no decryption)', actual_user=run(['id','-un']).stdout.strip()), indent=2)+'\n')
    return cz, entries


(ARTIFACTS/'expected-errors.txt').write_text('')
personal, pentries = profile('personal', 'as', 'personal')
work, wentries = profile('work', 'foodics', 'work')
# Read-only Git identity inheritance proof for linked worktrees outside Code/foodics.
repo = ARTIFACTS/'git-worktree-fixture'
repo.mkdir(exist_ok=True)
run(['git','init','--quiet',str(repo)])
for email, cz, entries in [('a.shahwan@foodics.com',work,wentries),('a.shahwan42@gmail.com',personal,pentries)]:
    file = ARTIFACTS/('work' if 'foodics' in email else 'personal')/'rendered/.gitconfig'
    env = dict(os.environ, GIT_CONFIG_GLOBAL=str(file), GIT_CONFIG_NOSYSTEM='1')
    for location in ['checkout', 'Code/worktrees/example/migration-123']:
        dest = ARTIFACTS/location
        dest.mkdir(parents=True,exist_ok=True)
        (dest/'.git').write_text('gitdir: '+str(repo/'.git')+'\n')
        result = subprocess.run(['git','-C',str(dest),'config','user.email'],env=env,text=True,capture_output=True)
        check(result.returncode == 0 and result.stdout.strip() == email, f'worktree identity inheritance failed: {result.stdout}{result.stderr}')
        result = subprocess.run(['git','-C',str(dest),'config','user.name'],env=env,text=True,capture_output=True)
        expected_name = 'A. S. Foodics' if 'foodics' in email else 'Ahmed Shahwan'
        check(result.returncode == 0 and result.stdout.strip() == expected_name, f'worktree full name inheritance failed: {result.stdout}{result.stderr}')
# Legacy empty-role Macs are resolved by username, rather than carrying both roles.
for cz, username, role in [(personal,'as','personal'),(work,'foodics','work')]:
    result = cz('--override-data', json.dumps({'kind':'mac','role':'','chezmoi':{'username':username}}), 'execute-template', '{{ includeTemplate "account-role" . }}')
    check(result.stdout == role, 'legacy empty role inference failed')
# Mismatched identity and unknown accounts fail closed.
for override in [{'role':'personal','chezmoi':{'username':'foodics'}}, {'role':'','chezmoi':{'username':'unknown'}}, {'username':'as','chezmoi':{'username':'foodics'}}]:
    result = work('--override-data',json.dumps(override),'execute-template','{{ includeTemplate "has-personal" . }}',check=False)
    check(result.returncode != 0, 'invalid account identity unexpectedly accepted')
    with (ARTIFACTS/'expected-errors.txt').open('a') as f:
        f.write(json.dumps(override)+'\n'+result.stdout+result.stderr+'\n')
# Role-scoped opt-in work consumers never gain personal references.
result = work('--override-data',json.dumps({'secret_integrations':True}), 'execute-template','--file',str(ROOT/'dot_config/zsh/secrets.zsh.tmpl'),str(ROOT/'dot_local/bin/executable_mcp-github-register.tmpl'))
check('xwug424' not in result.stdout and 'jypxox' not in result.stdout and 'i4fkk5' in result.stdout, 'opt-in token boundary failed')
# The opt-in EOD consumer must find new work commits as well as historical ones.
result = work('--override-data', json.dumps({'eod':True}), 'execute-template', '--file', str(ROOT/'dot_claude/skills/eod/SKILL.md.tmpl'))
check('A. S. Foodics' in result.stdout and 'A[.] S[.] Foodics' in result.stdout and 'A. S. Shahwan' not in result.stdout, 'EOD work identity mismatch')
# Compatibility renders retain their explicit Linux role, without accessing ciphertext.
profile('linux-personal','ubuntu','personal','vm')
profile('linux-work','ubuntu','work','vm')
verify_bootstrap(ROOT, ARTIFACTS)
run(['git','-C',str(ROOT),'diff','HEAD','--check'])
print('PASS: personal/work native and Linux renders, init, syntax, secret boundaries, linked-worktree identities, non-mutating diff/apply, invalid identity rejection.')
print('Audit artifacts:', ARTIFACTS)
