import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { spawn, spawnSync } from 'node:child_process';
import { createServer } from 'node:http';
import { inflateSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const assets = path.dirname(fileURLToPath(import.meta.url));
const revision = '39e97500725783490136a8fc7040e6e4dbaafa44';
const hash = f => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
const release = () => `${revision.slice(0, 12)}-${hash(path.join(assets, 'compat.patch')).slice(0, 12)}-${hash(path.join(assets, 'pnpm-lock.yaml')).slice(0, 12)}`;
const root = path.join(os.homedir(), '.local/share/expect-check/runtimes');
const runtime = () => path.join(root, release());
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
function command(bin, args, cwd, options = {}) {
  const r = spawnSync(bin, args, { cwd, encoding: 'utf8', timeout: 600000, ...options });
  if (r.error || r.status !== 0) throw new Error(`${bin} ${args.join(' ')}: ${r.error?.message ?? r.stderr ?? `exit ${r.status}`}`);
  return r.stdout?.trim() ?? '';
}
function codex(deadline = Date.now() + 5000) {
  const budget = () => { const remaining = deadline - Date.now(); if (remaining <= 0) throw new Error('Whole-run deadline exceeded during preflight'); return Math.min(remaining, 5000); };
  const bin = command('/bin/sh', ['-c', 'command -v codex'], undefined, { timeout: budget() });
  if (!path.isAbsolute(bin)) throw new Error('Native Codex CLI missing from PATH');
  return { path: fs.realpathSync(bin), version: command(bin, ['--version'], undefined, { timeout: budget() }) };
}
function inventory(dir, prefix = '') {
  const result = {};
  for (const entry of fs.readdirSync(path.join(dir, prefix), { withFileTypes: true })) {
    if (entry.name === '.git' || entry.name === 'runtime.json') continue;
    const rel = path.join(prefix, entry.name);
    if (entry.isDirectory()) Object.assign(result, inventory(dir, rel));
    else if (entry.isSymbolicLink()) result[rel] = `link:${fs.readlinkSync(path.join(dir, rel))}`;
    else if (entry.isFile()) result[rel] = hash(path.join(dir, rel));
  }
  return result;
}
export function verifyRuntime(dir = runtime(), deadline = Date.now() + 30000) {
  try {
    const manifest = JSON.parse(fs.readFileSync(path.join(dir, 'runtime.json')));
    if (manifest.release !== release() || manifest.revision !== revision || manifest.adapter !== '2.1.1') throw new Error('release mismatch');
    for (const [rel, expected] of Object.entries(manifest.files)) {
      if (Date.now() >= deadline) throw new Error('Whole-run deadline exceeded during preflight');
      const f = path.join(dir, rel);
      const actual = expected.startsWith('link:') ? `link:${fs.readlinkSync(f)}` : hash(f);
      if (actual !== expected) throw new Error(`mismatch: ${rel}`);
    }
    const entry = path.join(dir, 'apps/cli/dist/index.js');
    if (!fs.existsSync(entry)) throw new Error('CLI missing');
    const req = createRequire(entry);
    if (req('@agentclientprotocol/codex-acp/package.json').version !== '2.1.1') throw new Error('adapter mismatch');
    return { ...manifest, entry, codex: codex(deadline) };
  } catch (e) { throw new Error(`Private Expect runtime unavailable (${e.message}). Run expect-check setup.`); }
}
export async function ownedProcess(bin, args, { cwd, env, timeoutMs, stdoutFile, stderrFile, signal } = {}) {
  const out = fs.createWriteStream(stdoutFile);
  const err = fs.createWriteStream(stderrFile);
  const ledger = `${stdoutFile}.process-ledger.ndjson`;
  fs.writeFileSync(ledger, '');
  const ownedEnv = { ...env, EXPECT_PROCESS_LEDGER: ledger, NODE_OPTIONS: `${env?.NODE_OPTIONS ?? ''} --import ${JSON.stringify(path.join(assets, 'process-owner.mjs'))}`.trim() };
  const child = spawn(bin, args, { cwd, env: ownedEnv, detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
  const ledgerRecords = () => {
    if (!fs.existsSync(ledger)) return [];
    return fs.readFileSync(ledger, 'utf8').split('\n').filter(Boolean).map(line => { try { return JSON.parse(line); } catch { return null; } }).filter(Boolean);
  };
  const registered = () => ledgerRecords().filter(record => record.identity && Number.isInteger(record.pid));
  const processTable = () => command('ps', ['-axo', 'pid=,pgid=,stat=,lstart=']).split('\n').flatMap(line => {
    const fields = line.trim().split(/\s+/);
    return fields.length >= 8 && !fields[2].startsWith('Z') ? [{ pid: Number(fields[0]), group: Number(fields[1]), identity: fields.slice(3).join(' ') }] : [];
  });
  const liveOwned = () => {
    const table = processTable();
    return registered().flatMap(record => {
      const leader = table.find(item => item.pid === record.pid);
      if (leader && leader.identity !== record.identity.replace(/\s+/g, ' ')) return [];
      // POSIX keeps a process-group ID reserved while any member survives its leader.
      return record.detached ? table.filter(item => item.group === record.pid).map(item => ({ ...item, detached: true, group: record.pid })) :
        leader ? [{ ...leader, detached: false }] : [];
    });
  };
  const killOwned = sig => {
    // Validate the recorded start identity before signalling a PID or its detached group.
    for (const record of liveOwned()) { try { process.kill(record.detached ? -record.group : record.pid, sig); } catch {} }
    if (child.pid) { try { process.kill(-child.pid, sig); } catch {} }
  };
  let outcome;
  let childError;
  let hardKill;
  const stop = status => {
    outcome ??= status;
    killOwned('SIGTERM');
    hardKill ??= setTimeout(() => killOwned('SIGKILL'), 1000);
  };
  const cancel = () => stop(130);
  process.once('SIGINT', cancel); process.once('SIGTERM', cancel);
  signal?.addEventListener('abort', cancel, { once: true });
  const timer = setTimeout(() => stop(124), timeoutMs);
  if (signal?.aborted) cancel();
  child.stdout.on('data', data => { out.write(data); process.stdout.write(data); });
  child.stderr.on('data', data => { err.write(data); process.stderr.write(data); });
  let nativeOffset = 0, nativePending = '';
  const nativeLog = ownedEnv.APP_SERVER_LOGS ? path.join(ownedEnv.APP_SERVER_LOGS, 'app-server.log') : undefined;
  const nativeExitStatuses = [];
  let nativeFailure;
  const streamNativeDiagnostics = () => {
    if (!nativeLog || !fs.existsSync(nativeLog)) return;
    const size = fs.statSync(nativeLog).size;
    if (size <= nativeOffset) return;
    const fd = fs.openSync(nativeLog, 'r');
    const data = Buffer.alloc(size - nativeOffset);
    fs.readSync(fd, data, 0, data.length, nativeOffset); fs.closeSync(fd); nativeOffset = size;
    const lines = (nativePending + data.toString()).split('\n'); nativePending = lines.pop();
    for (const line of lines) {
      if (/^(?:\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} )?\[(ERR|EXIT|SYSTEM_ERROR)\]/.test(line)) { err.write(line + '\n'); process.stderr.write(line + '\n'); }
      const exit = line.match(/\[EXIT\] code: (\d+)/); if (exit) nativeExitStatuses.push(Number(exit[1]));
      try {
        const notification = JSON.parse(line.slice(line.indexOf('{')));
        if (notification.method === 'error' && notification.params?.willRetry === false) {
          const message = notification.params.error?.message;
          if (typeof message === 'string') {
            nativeFailure ??= message;
            err.write(`Native Codex error: ${message}\n`); process.stderr.write(`Native Codex error: ${message}\n`);
            stop(2);
          }
        }
      } catch {}
      if (/^(?:\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} )?\[SYSTEM_ERROR\]/.test(line)) { nativeFailure ??= line; stop(2); }

    }
  };
  const nativeTimer = setInterval(streamNativeDiagnostics, 200);
  const result = await new Promise(resolve => {
    child.once('error', e => { childError = e.message; resolve({ code: null, signal: null }); });
    child.once('exit', (code, sig) => resolve({ code, signal: sig }));
  });
  clearTimeout(timer); clearTimeout(hardKill);
  // A daemon can outlive a normally completed CLI, so always clean its owned group.
  if (child.pid) {
    killOwned('SIGTERM');
    await sleep(1000);
    killOwned('SIGKILL');
    await sleep(100);
  }
  clearInterval(nativeTimer); streamNativeDiagnostics();
  process.removeListener('SIGINT', cancel); process.removeListener('SIGTERM', cancel);
  signal?.removeEventListener('abort', cancel);
  await Promise.all([new Promise(r => out.end(r)), new Promise(r => err.end(r))]);
  const groups = command('ps', ['-axo', 'pid=,pgid=,stat=,command=']);
  const survivors = child.pid ? groups.split('\n').filter(line => {
    const fields = line.trim().split(/\s+/); return Number(fields[1]) === child.pid && !fields[2].startsWith('Z');
  }) : [];
  return { ...result, nativeFailure, nativeExits: ledgerRecords().filter(r => r.kind === 'nativeExit'), nativeExitStatuses: [...nativeExitStatuses, ...ledgerRecords().filter(r => r.kind === 'nativeExit' && Number.isInteger(r.code)).map(r => r.code)], outcome, childError, processGroup: child.pid, ownedProcesses: registered(), survivors: [...survivors, ...liveOwned().map(r => `registered PID ${r.pid}`)] };
}
export function readReport(raw) {
  // Native shutdown diagnostics can follow the completed report on verbose stdout.
  const reports = [];
  for (const match of raw.matchAll(/(?:^|\n)(\{)/g)) {
    const start = match.index + match[0].length - 1;
    let depth = 0, quoted = false, escaped = false;
    for (let i = start; i < raw.length; i++) {
      const char = raw[i];
      if (quoted) { if (escaped) escaped = false; else if (char === '\\') escaped = true; else if (char === '"') quoted = false; continue; }
      if (char === '"') quoted = true;
      else if (char === '{') depth++;
      else if (char === '}' && --depth === 0) {
        try { const value = JSON.parse(raw.slice(start, i + 1)); if (value && typeof value.status === 'string' && Array.isArray(value.steps) && value.artifacts) reports.push(value); } catch {}
        break;
      }
    }
  }
  if (reports.length === 1) return reports[0];
  throw new Error('Missing, malformed, or ambiguous completed JSON report');
}
export function validatePng(data) {
  if (data.length < 57 || data.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a') throw new Error('Invalid PNG signature');
  let offset = 8; let header; const compressed = []; let ended = false;
  const crc32 = bytes => { let crc = 0xffffffff; for (const byte of bytes) { crc ^= byte; for (let i=0;i<8;i++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0); } return (crc ^ 0xffffffff) >>> 0; };
  while (offset + 12 <= data.length) {
    const size = data.readUInt32BE(offset); const type = data.subarray(offset + 4, offset + 8).toString();
    if (offset + size + 12 > data.length || crc32(data.subarray(offset + 4, offset + 8 + size)) !== data.readUInt32BE(offset + 8 + size)) throw new Error('Invalid PNG chunk or checksum');
    const chunk = data.subarray(offset + 8, offset + 8 + size);
    if (!header && type !== 'IHDR') throw new Error('PNG header missing');
    if (type === 'IHDR') { if (header || size !== 13) throw new Error('Invalid PNG header'); header = chunk; }
    if (type === 'IDAT') compressed.push(chunk);
    offset += size + 12;
    if (type === 'IEND') { if (size || offset !== data.length) throw new Error('Invalid PNG ending'); ended = true; break; }
  }
  if (!ended || !compressed.length || !header.readUInt32BE(0) || !header.readUInt32BE(4) || header[8] !== 8 || ![0,2,4,6].includes(header[9]) || header[10] || header[11] || header[12]) throw new Error('Unsupported or malformed PNG image');
  const width = header.readUInt32BE(0), height = header.readUInt32BE(4);
  const bytesPerPixel = {0:1,2:3,4:2,6:4}[header[9]]; const stride = 1 + width * bytesPerPixel;
  if (stride * height > 67108864) throw new Error('PNG exceeds inspection limit');
  const pixels = inflateSync(Buffer.concat(compressed), { maxOutputLength: 67108864 });
  if (pixels.length !== stride * height) throw new Error('Malformed PNG pixels');
  for (let row = 0; row < height; row++) if (pixels[row * stride] > 4) throw new Error('Invalid PNG filter');
}
export function classify(report, child, artifactRoot) {
  if (child.outcome) return { exit: child.outcome, reason: child.outcome === 124 ? 'Whole-run deadline exceeded' : child.outcome === 130 ? 'Cancelled' : child.nativeFailure ?? 'Native Codex infrastructure failure' };
  if (child.childError || child.survivors?.length) return { exit: 2, reason: child.childError ?? 'Owned processes survived cleanup' };
  if (!report || !['passed', 'failed'].includes(report.status) || !Array.isArray(report.steps) || !report.steps.length ||
      typeof report.title !== 'string' || typeof report.summary !== 'string' || !Number.isFinite(report.duration_ms))
    return { exit: 2, reason: 'Missing, malformed, or incomplete report' };
  const steps = report.steps;
  if (steps.some(s => !s.title || !['passed', 'failed', 'skipped', 'not-run'].includes(s.status))) return { exit: 2, reason: 'Report contains unexecuted or invalid steps' };
  if (child.code !== (report.status === 'passed' ? 0 : 1)) return { exit: 2, reason: `Child status ${child.code} contradicts report ${report.status}` };
  if (report.status === 'passed' && steps.some(s => s.status !== 'passed') || report.status === 'failed' && !steps.some(s => s.status === 'failed'))
    return { exit: 2, reason: 'Step results contradict report status' };
  const screenshots = report.artifacts?.screenshots;
  if (!Array.isArray(screenshots) || !screenshots.length) return { exit: 2, reason: 'No screenshots to inspect' };
  const inspected = [];
  try {
    const base = fs.realpathSync(artifactRoot) + path.sep;
    const all = [...screenshots, ...[report.artifacts.video, report.artifacts.replay].filter(Boolean)];
    for (const f of all) {
      const absolute = fs.realpathSync(f);
      if (!absolute.startsWith(base)) throw new Error(`Artifact outside run: ${f}`);
      const data = fs.readFileSync(absolute);
      if (!data.length) throw new Error(`Empty artifact: ${f}`);
      if (screenshots.includes(f)) validatePng(data);
      inspected.push({ path: absolute, bytes: data.length, sha256: hash(absolute) });
    }
  } catch (e) { return { exit: 2, reason: e.message }; }
  return { exit: report.status === 'passed' ? 0 : 1, reason: report.summary, inspected };
}
function ignoredOutput(dir) {
  fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  if (fs.readdirSync(dir).length) throw new Error('Output directory must be empty: use a new directory per run');
  const r = spawnSync('git', ['-C', dir, 'rev-parse', '--show-toplevel'], { encoding: 'utf8' });
  if (r.status === 0) {
    const probe = path.join(dir, '.expect-evidence-probe');
    const check = spawnSync('git', ['-C', r.stdout.trim(), 'check-ignore', '--no-index', '--quiet', probe]);
    if (check.status !== 0) throw new Error('Output directory must be ignored by Git');
  }
}
async function locked(action) {
  const lock = path.join(os.homedir(), '.local/state/expect-check/lock');
  fs.mkdirSync(path.dirname(lock), { recursive: true });
  try { fs.mkdirSync(lock); } catch { throw new Error(`Expect runner busy or stale lock: ${lock}. Verify its owner before removing it.`); }
  fs.writeFileSync(path.join(lock, 'owner.json'), JSON.stringify({ pid: process.pid, started: new Date().toISOString() }));
  try { return await action(); } finally { fs.rmSync(lock, { recursive: true, force: true }); }
}
async function setup() {
  return locked(async () => {
    if (fs.existsSync(runtime())) {
      try { verifyRuntime(); console.log(`Runtime ready: ${runtime()}`); return; }
      catch (e) { console.error(`Rebuilding invalid private runtime: ${e.message}`); }
    }
    fs.mkdirSync(root, { recursive: true });
    const staging = fs.mkdtempSync(path.join(root, '.build-'));
    try {
      command('git', ['init', '--quiet', staging]);
      command('git', ['remote', 'add', 'origin', 'https://github.com/millionco/expect.git'], staging);
      command('git', ['fetch', '--depth=1', 'origin', revision], staging, { stdio: 'inherit' });
      command('git', ['checkout', '--quiet', '--detach', 'FETCH_HEAD'], staging);
      if (command('git', ['rev-parse', 'HEAD'], staging) !== revision) throw new Error('Source revision mismatch');
      command('git', ['apply', '--check', path.join(assets, 'compat.patch')], staging);
      command('git', ['apply', path.join(assets, 'compat.patch')], staging);
      fs.copyFileSync(path.join(assets, 'pnpm-lock.yaml'), path.join(staging, 'pnpm-lock.yaml'));
      if (command('pnpm', ['--version'], staging) !== '10.29.1') throw new Error('Setup requires pnpm 10.29.1');
      command('pnpm', ['install', '--frozen-lockfile', '--filter', 'expect-cli...'], staging, { stdio: 'inherit' });
      command('pnpm', ['--filter', 'expect-cli...', 'build'], staging, { stdio: 'inherit' });
      command('pnpm', ['--filter', '@expect/agent', 'typecheck'], staging, { stdio: 'inherit' });
      command('pnpm', ['--filter', '@expect/agent', 'exec', 'vp', 'test', 'run', 'tests/acp-operation-guard.test.ts'], staging, { stdio: 'inherit' });
      command('pnpm', ['--filter', 'expect-cli', 'exec', 'vp', 'test', 'run', 'tests/extract-close-artifacts.test.ts'], staging, { stdio: 'inherit' });
      const manifest = { release: release(), revision, adapter: '2.1.1', pnpm: '10.29.1', node: process.version, built: new Date().toISOString(), files: inventory(staging) };
      fs.writeFileSync(path.join(staging, 'runtime.json'), JSON.stringify(manifest, null, 2));
      const previous = `${runtime()}.replaced-${Date.now()}`;
      if (fs.existsSync(runtime())) fs.renameSync(runtime(), previous);
      try { fs.renameSync(staging, runtime()); verifyRuntime(); }
      catch (e) {
        if (fs.existsSync(runtime())) fs.rmSync(runtime(), { recursive: true, force: true });
        if (fs.existsSync(previous)) fs.renameSync(previous, runtime());
        throw e;
      }
      if (fs.existsSync(previous)) fs.rmSync(previous, { recursive: true, force: true }); console.log(`Runtime ready: ${runtime()}`);
    } finally { if (fs.existsSync(staging)) fs.rmSync(staging, { recursive: true, force: true }); }
  });
}
function options(args) {
  const result = {};
  for (let i = 0; i < args.length; i += 2) {
    if (!['--url', '--instruction', '--target', '--output-dir', '--agent', '--timeout-ms'].includes(args[i]) || !args[i + 1] || args[i + 1].startsWith('--')) throw new Error(`Invalid option: ${args[i]}`);
    if (Object.hasOwn(result, args[i])) throw new Error(`Duplicate option: ${args[i]}`);
    result[args[i].slice(2)] = args[i + 1];
  }
  return result;
}
const smokeInstruction = 'Only test the disposable counter page at the supplied URL. Using the browser tools, verify Count: 0 initially, click Increment exactly once and assert Count: 1 visibly. Capture a PNG screenshot after the click even on failure, inspect it, then close the browser to flush artifacts. Do not change any source or inspect implementation. Report a failed test if the visible count stays 0. Do not add unrelated checks.';
async function run(opts, smoke) {
  const dir = path.resolve(opts['output-dir'] ?? '');
  if (!opts['output-dir']) throw new Error('--output-dir is required');
  const agent = opts.agent ?? 'codex';
  const target = opts.target ?? 'changes';
  const timeoutMs = Number(opts['timeout-ms'] ?? (smoke ? 120000 : 300000));
  if (!['codex', 'claude'].includes(agent) || !['changes', 'unstaged', 'branch'].includes(target) || !Number.isSafeInteger(timeoutMs) || timeoutMs <= 0 || timeoutMs > 3600000) throw new Error('Invalid agent, target, or timeout');
  if (!smoke && (!opts.url || !opts.instruction || !opts.target)) throw new Error('run requires --url, --instruction, and --target');
  if (smoke && (opts.url || opts.instruction || opts.target || opts.agent)) throw new Error('smoke uses the healthy fixture, Codex, and fixed expectation');
  if (!smoke && !['http:', 'https:'].includes(new URL(opts.url).protocol)) throw new Error('Expected an HTTP origin');
  return locked(async () => {
    ignoredOutput(dir);
    const started = Date.now();
    let cancelled = false;
    const cancelPreflight = () => { cancelled = true; };
    process.on('SIGINT', cancelPreflight); process.on('SIGTERM', cancelPreflight);
    const remaining = () => { if (cancelled) throw new Error('Cancelled during preflight'); const ms = timeoutMs - (Date.now() - started); if (ms <= 0) throw new Error('Whole-run deadline exceeded during preflight'); return ms; };
    const preflightCommand = async (bin, args, cwd) => {
      await sleep(0); const result = command(bin, args, cwd, { timeout: remaining() }); await sleep(0); remaining(); return result;
    };
    let server;
    let fixture;
    let meta = { sourceRevision: revision, agent, target, timeoutMs, started: new Date(started).toISOString() };
    let report;
    let child = {};
    let classification;
    try {
      const ready = verifyRuntime(runtime(), started + timeoutMs);
      meta = { ...meta, release: ready.release, runtime: runtime(), node: process.version, codex: ready.codex, adapter: ready.adapter, expect: '0.1.3' };
      if (smoke) {
        fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'expect-counter-'));
        fs.copyFileSync(path.join(assets, 'counter.html'), path.join(fixture, 'index.html'));
        await preflightCommand('git', ['init', '--quiet', fixture]);
        await preflightCommand('git', ['add', 'index.html'], fixture);
        await preflightCommand('git', ['-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', '-c', 'user.name=Ahmed', '-c', 'user.email=fixture@localhost', 'commit', '--quiet', '-m', 'Counter fixture'], fixture);
        server = createServer((_req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(fs.readFileSync(path.join(fixture, 'index.html'))); });
        await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
        opts.url = `http://127.0.0.1:${server.address().port}`;
        meta.fixtureSha256 = hash(path.join(fixture, 'index.html'));
      }
      await sleep(0); remaining();
      meta.origin = opts.url;
      meta.instruction = smoke ? smokeInstruction : opts.instruction;
      const artifacts = path.join(dir, 'artifacts'); fs.mkdirSync(artifacts);
      const env = { ...process.env, APP_SERVER_LOGS: path.join(dir, 'adapter'), CODEX_PATH: ready.codex.path, EXPECT_SESSION_FILE: path.join(dir, 'browser-session.json'), EXPECT_ARTIFACT_DIR: artifacts, EXPECT_HEADED: 'false', EXPECT_COOKIE_BROWSERS: '' };
      delete env.EXPECT_CDP_URL; delete env.EXPECT_PROFILE;
      child = await ownedProcess(process.execPath, [ready.entry, 'tui', '--agent', agent, '--verbose', '--browser-mode', 'headless', '--no-cookies', '--output', 'json', '-u', opts.url, '-m', meta.instruction, '-y', '--timeout', String(timeoutMs), '--target', target], {
        cwd: fixture ?? process.cwd(), env, timeoutMs: Math.max(1, timeoutMs - (Date.now() - started)), stdoutFile: path.join(dir, 'stdout.log'), stderrFile: path.join(dir, 'stderr.log'),
      });
      try { report = readReport(fs.readFileSync(path.join(dir, 'stdout.log'), 'utf8')); } catch (e) { meta.reportError = e.message; }
      classification = classify(report, child, artifacts);
      if (smoke && hash(path.join(fixture, 'index.html')) !== meta.fixtureSha256) classification = { exit: 2, reason: 'Fixture source changed during verification' };
      if (report) fs.writeFileSync(path.join(dir, 'report.json'), JSON.stringify(report, null, 2));
    } catch (e) { classification = { exit: cancelled ? 130 : Date.now() - started >= timeoutMs ? 124 : 2, reason: e.message }; }
    finally {
      if (server) { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
      if (fixture) fs.rmSync(fixture, { recursive: true, force: true });
      process.removeListener('SIGINT', cancelPreflight); process.removeListener('SIGTERM', cancelPreflight);
    }
    fs.writeFileSync(path.join(dir, 'result.json'), JSON.stringify({ ...meta, elapsedMs: Date.now() - started, child, ...classification }, null, 2));
    console.error(`expect-check: ${classification.reason}; exit ${classification.exit}; evidence ${dir}`);
    return classification.exit;
  });
}
export async function main(args = process.argv.slice(2)) {
  const [subcommand, ...rest] = args;
  if (subcommand === 'setup' && !rest.length) { await setup(); return 0; }
  if (subcommand === 'doctor' && !rest.length) { console.log(JSON.stringify(verifyRuntime(), (key, value) => key === 'files' ? `${Object.keys(value).length} verified files` : value, 2)); return 0; }
  if (subcommand === 'run' || subcommand === 'smoke') return run(options(rest), subcommand === 'smoke');
  throw new Error('Usage: expect-check setup | doctor | smoke --output-dir DIR | run --url ORIGIN --instruction TEXT --target changes|unstaged|branch --output-dir DIR [--agent codex|claude] [--timeout-ms MS]');
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().then(code => { process.exitCode = code; }).catch(e => { console.error(`expect-check: ${e.message}`); process.exitCode = 2; });
}
