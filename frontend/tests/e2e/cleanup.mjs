import { spawn } from "node:child_process";
import os from "node:os";
import path from "node:path";

export default async function cleanup() {
  const directory = process.env.BRANDGUARD_E2E_DATA_DIR;
  if (!directory) return;

  const target = path.resolve(directory);
  if (path.dirname(target) !== os.tmpdir() || !path.basename(target).startsWith("brandguard-e2e-")) return;

  // Playwright stops webServer after globalTeardown. Retry after it releases
  // SQLite and Chroma file handles on Windows.
  const retryScript = [
    'const fs = require("node:fs");',
    `const target = ${JSON.stringify(target)};`,
    "let attempts = 0;",
    'const timer = setInterval(() => { try { fs.rmSync(target, { recursive: true, force: true, maxRetries: 2, retryDelay: 100 }); clearInterval(timer); process.exit(0); } catch { if (++attempts >= 60) { clearInterval(timer); process.exit(0); } } }, 2000);',
  ].join("\n");
  const child = spawn(process.execPath, ["-e", retryScript], {
    detached: true,
    stdio: "ignore",
    windowsHide: true,
  });
  child.unref();
}
