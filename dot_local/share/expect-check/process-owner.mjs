// Loaded only in runner-owned Node processes, including browser daemons.
import fs from 'node:fs';
import childProcess from 'node:child_process';
import { syncBuiltinESMExports } from 'node:module';
const ledger = process.env.EXPECT_PROCESS_LEDGER;
if (ledger) {
  const original = childProcess.spawn;
  childProcess.spawn = function (...args) {
    const child = original.apply(this, args);
    if (child.pid) {
      const identity = childProcess.spawnSync('ps', ['-p', String(child.pid), '-o', 'lstart='], { encoding: 'utf8' }).stdout?.trim();
      if (identity) fs.appendFileSync(ledger, JSON.stringify({ pid: child.pid, parent: process.pid, identity, detached: Boolean(args[2]?.detached ?? (Array.isArray(args[1]) ? false : args[1]?.detached)) }) + '\n');
    }
    if (child.pid && args[0] === process.env.CODEX_PATH && args[1]?.[0] === 'app-server') {
      // The maintained adapter otherwise drops native stderr without optional logging,
      // and an immediate native exit can become an unhandled stdin EPIPE.
      child.stderr?.on('data', data => { try { fs.writeSync(2, data); } catch {} });
      child.stdin?.on('error', error => { try { fs.writeSync(2, `Native Codex stdin: ${error.message}\n`); } catch {} });
      child.once('close', (code, signal) => {
        fs.appendFileSync(ledger, JSON.stringify({ kind: 'nativeExit', pid: child.pid, code, signal }) + '\n');
        try { fs.writeSync(2, `Native Codex app-server exited: status ${code}, signal ${signal}\n`); } catch {}
        // Provider replacement and normal shutdown deliberately end stdin.
        // Only an unexpected engine loss invalidates the ACP host.
        if (!child.stdin?.writableEnded) process.exit(code ?? 1);
      });
    }
    return child;
  };
  syncBuiltinESMExports();
}
