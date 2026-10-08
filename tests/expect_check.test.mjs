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
  assert.deepEqual(readReport(`log { diagnostics }\n${JSON.stringify({...report, summary: 'quoted \" } brace'})}\n[WARN] shutdown { diagnostic }`), {...report, summary: 'quoted \" } brace'});
  assert.throws(() => readReport(`${JSON.stringify(report)}\n${JSON.stringify(report)}`), /ambiguous/);
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

test('native adapter diagnostics retain the original cause and native status', async () => {
  const logDir = path.join(dir, 'adapter'); fs.mkdirSync(logDir);
  const result = await ownedProcess(process.execPath, ['-e', `require('fs').writeFileSync(require('path').join(process.env.APP_SERVER_LOGS,'app-server.log'),'[ERR] exact native configuration cause\\n[EXIT] code: 7\\n');process.exit(1)`], {
    timeoutMs: 5000, stdoutFile: path.join(dir, 'native-out'), stderrFile: path.join(dir, 'native-err'), env: { ...process.env, APP_SERVER_LOGS: logDir },
  });
  assert.equal(result.code, 1); assert.deepEqual(result.nativeExitStatuses, [7]);
  assert.match(fs.readFileSync(path.join(dir, 'native-err'), 'utf8'), /exact native configuration cause/);
});

test('an immediate native engine exit preserves stderr and rejects its ACP host promptly', async () => {
  const native = path.join(dir, 'fake-codex');
  fs.writeFileSync(native, '#!/bin/sh\nprintf "%s\\n" "native config: unknown tier" >&2\nexit 7\n', { mode: 0o700 });
  const started = Date.now();
  const result = await ownedProcess(process.execPath, ['-e', `const child=require('child_process').spawn(process.env.CODEX_PATH,['app-server']);child.stdin.write('initialize\\n');setInterval(()=>{},1000);`], {
    timeoutMs: 5000, stdoutFile: path.join(dir, 'immediate-out'), stderrFile: path.join(dir, 'immediate-err'), env: { ...process.env, CODEX_PATH: native },
  });
  assert.equal(result.code, 7); assert.deepEqual(result.nativeExitStatuses, [7]);
  assert.match(fs.readFileSync(path.join(dir, 'immediate-err'), 'utf8'), /native config: unknown tier/);
  assert.deepEqual(result.survivors, []); assert.ok(Date.now()-started < 4000);
});

 test('intentional native shutdown permits a replacement engine', async () => {
  const native = path.join(dir, 'replace-codex');
  fs.writeFileSync(native, '#!/bin/sh\ncat >/dev/null\nexit 0\n', { mode: 0o700 });
  const result = await ownedProcess(process.execPath, ['-e', `const cp=require('child_process');const first=cp.spawn(process.env.CODEX_PATH,['app-server']);first.once('close',()=>{const replacement=cp.spawn(process.env.CODEX_PATH,['app-server']);replacement.once('close',()=>{console.log('replacement completed');process.exit(0)});replacement.stdin.end()});first.stdin.end();`], {
    timeoutMs: 5000, stdoutFile: path.join(dir, 'replacement-out'), stderrFile: path.join(dir, 'replacement-err'), env: { ...process.env, CODEX_PATH: native },
  });
  assert.equal(result.code, 0);
  assert.match(fs.readFileSync(path.join(dir, 'replacement-out'), 'utf8'), /replacement completed/);
  assert.equal(result.nativeExits.length, 2);
  assert.deepEqual(result.survivors, []);
});

test('a terminal native provider error preserves its exact cause and fails promptly', async () => {
  const logDir = path.join(dir, 'quota'); fs.mkdirSync(logDir);
  const message = 'You’ve hit your usage limit. Try again at 5:17 PM.';
  const notification = JSON.stringify({method:'error',params:{error:{message,codexErrorInfo:'usageLimitExceeded'},willRetry:false}});
  const start = Date.now();
  const result = await ownedProcess(process.execPath, ['-e', `require('fs').writeFileSync(require('path').join(process.env.APP_SERVER_LOGS,'app-server.log'), ${JSON.stringify(notification+'\n')});setInterval(()=>{},1000)`], {
    timeoutMs: 10000, stdoutFile: path.join(dir, 'quota-out'), stderrFile: path.join(dir, 'quota-err'), env: {...process.env,APP_SERVER_LOGS:logDir},
  });
  assert.equal(result.outcome,2); assert.equal(classify(undefined,result,dir).exit,2);
  assert.equal(result.nativeFailure,message); assert.match(fs.readFileSync(path.join(dir,'quota-err'),'utf8'),/usage limit/);
  assert.deepEqual(result.survivors,[]); assert.ok(Date.now()-start<4000);
});

test('ordinary output with an error-tag literal and retryable errors remain nonterminal', async () => {
  const logDir = path.join(dir, 'literal'); fs.mkdirSync(logDir);
  const text = '2026-10-08 13:41:53,562 [OUT] '+JSON.stringify({method:'item/agentMessage/delta',params:{delta:'Page displays [SYSTEM_ERROR]'}})+'\n'+JSON.stringify({method:'error',params:{error:{message:'Transient transport error'},willRetry:true}})+'\n';
  const result = await ownedProcess(process.execPath, ['-e', `require('fs').writeFileSync(require('path').join(process.env.APP_SERVER_LOGS,'app-server.log'),${JSON.stringify(text)});setTimeout(()=>process.exit(0),400)`], {
    timeoutMs: 5000, stdoutFile:path.join(dir,'literal-out'),stderrFile:path.join(dir,'literal-err'),env:{...process.env,APP_SERVER_LOGS:logDir},
  });
  assert.equal(result.code,0); assert.equal(result.outcome,undefined); assert.equal(result.nativeFailure,undefined);
  assert.deepEqual(result.survivors,[]);
});
