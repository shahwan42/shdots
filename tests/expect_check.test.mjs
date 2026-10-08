import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { classify, readReport, ownedProcess, validatePng } from '../dot_local/share/expect-check/runner.mjs';

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'expect-runner-test-'));
const png = path.join(dir, 'image.png');
fs.writeFileSync(png, Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==', 'base64'));
const report = { status: 'passed', title: 'Counter', summary: '1 passed', duration_ms: 10, steps: [{ title: 'Increment', status: 'passed' }], artifacts: { screenshots: [png] } };
const child = { code: 0, survivors: [] };
test('only a complete report with executed steps and inspected artifacts passes', () => {
  assert.equal(classify(report, child, dir).exit, 0);
  assert.equal(classify({ ...report, steps: [] }, child, dir).exit, 2);
  assert.equal(classify({ ...report, steps: [{ title: 'Click', status: 'not-run' }] }, child, dir).exit, 2);
  assert.equal(classify({ ...report, artifacts: {} }, child, dir).exit, 2);
  assert.equal(classify(report, { ...child, code: 7 }, dir).exit, 2);
  assert.equal(classify({ ...report, artifacts: { screenshots: ['/missing.png'] } }, child, dir).exit, 2);
});
test('failed browser steps map to test failure, infrastructure and timeout stay distinct', () => {
  const failed = { ...report, status: 'failed', steps: [{ title: 'Increment', status: 'failed', error: 'Count remained 0' }] };
  assert.equal(classify(failed, { ...child, code: 1 }, dir).exit, 1);
  assert.equal(classify({ ...failed, steps: [...failed.steps, { title: 'Downstream', status: 'not-run' }] }, { ...child, code: 1 }, dir).exit, 1);
  assert.equal(classify(undefined, { ...child, code: 1 }, dir).exit, 2);
  assert.equal(classify(report, { ...child, outcome: 124 }, dir).exit, 124);
  assert.equal(classify(report, { ...child, outcome: 130 }, dir).exit, 130);
});
test('verbose output is supported, incomplete JSON is rejected', () => {
  assert.deepEqual(readReport(`log { diagnostics }\n${JSON.stringify(report)}\n`), report);
  assert.throws(() => readReport('{"status":"passed"'), /malformed/);
});
test('deadline kills a SIGTERM-ignoring child and its descendant', async () => {
  const start = Date.now();
  const result = await ownedProcess(process.execPath, ['-e', `process.on('SIGTERM',()=>{});require('child_process').spawn(process.execPath,['-e',"process.on('SIGTERM',()=>{});setInterval(()=>{},1000)"],{stdio:'ignore'});setInterval(()=>{},1000)`], {
    timeoutMs: 300, stdoutFile: path.join(dir, 'timeout-out'), stderrFile: path.join(dir, 'timeout-err'), env: process.env,
  });
  assert.equal(result.outcome, 124);
  assert.equal(result.signal, 'SIGKILL');
  assert.deepEqual(result.survivors, []);
  assert.ok(Date.now() - start < 6000);
});
test('cancellation preserves its classification and cleans owned processes', async () => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 200);
  const result = await ownedProcess(process.execPath, ['-e', 'setInterval(()=>{},1000)'], {
    timeoutMs: 10000, stdoutFile: path.join(dir, 'cancel-out'), stderrFile: path.join(dir, 'cancel-err'), env: process.env, signal: controller.signal,
  });
  clearTimeout(timer);
  assert.equal(result.outcome, 130);
  assert.deepEqual(result.survivors, []);
});
test('early child exit retains exact stderr and child exit status', async () => {
  const result = await ownedProcess(process.execPath, ['-e', 'console.error("config.toml:6:16: unknown variant default");process.exit(9)'], {
    timeoutMs: 5000, stdoutFile: path.join(dir, 'exit-out'), stderrFile: path.join(dir, 'exit-err'), env: process.env,
  });
  assert.equal(result.code, 9);
  assert.equal(fs.readFileSync(path.join(dir, 'exit-err'), 'utf8'), 'config.toml:6:16: unknown variant default\n');
});

test('detached SIGTERM-ignoring descendants are registered and killed', async () => {
  const result = await ownedProcess(process.execPath, ['-e', `process.on('SIGTERM',()=>{});require('child_process').spawn(process.execPath,['-e',"process.on('SIGTERM',()=>{});setInterval(()=>{},1000)"],{stdio:'ignore',detached:true}).unref();setInterval(()=>{},1000)`], {
    timeoutMs: 500, stdoutFile: path.join(dir, 'detached-out'), stderrFile: path.join(dir, 'detached-err'), env: process.env,
  });
  assert.equal(result.outcome, 124);
  assert.ok(result.ownedProcesses.some(p => p.detached));
  assert.deepEqual(result.survivors, []);
});
test('fabricated or checksum-corrupt PNGs are rejected', () => {
  const fake = Buffer.alloc(45); Buffer.from('89504e470d0a1a0a','hex').copy(fake); fake.writeUInt32BE(1,16); fake.writeUInt32BE(1,20); fake.write('IEND',37);
  assert.throws(() => validatePng(fake));
  const corrupt = Buffer.from(fs.readFileSync(png)); corrupt[30] ^= 1;
  assert.throws(() => validatePng(corrupt), /checksum/);
});

test('detached groups remain owned after their native leader exits', async () => {
  const marker = path.join(dir, 'grandchild.pid');
  const result = await ownedProcess(process.execPath, ['-e', `require('child_process').spawn('/bin/sh',['-c',"sleep 30 & echo $! > ${marker}; sleep 0.15"],{stdio:'ignore',detached:true}).unref();setTimeout(()=>process.exit(0),600)`], {
    timeoutMs: 5000, stdoutFile: path.join(dir, 'leader-out'), stderrFile: path.join(dir, 'leader-err'), env: process.env,
  });
  assert.equal(result.code, 0);
  const pid = Number(fs.readFileSync(marker, 'utf8').trim());
  const status = spawnSync('ps', ['-p', String(pid), '-o', 'stat='], { encoding: 'utf8' }).stdout.trim();
  assert.ok(!status || status.startsWith('Z'), `Native grandchild ${pid} survived: ${status}`);
  assert.ok(result.ownedProcesses.some(p => p.detached));
  assert.deepEqual(result.survivors, []);
});
