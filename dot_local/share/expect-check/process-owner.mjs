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
    return child;
  };
  syncBuiltinESMExports();
}
