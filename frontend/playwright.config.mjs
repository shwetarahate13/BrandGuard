import { defineConfig } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendDir, "..");
const dataDir = mkdtempSync(path.join(os.tmpdir(), "brandguard-e2e-"));
process.env.BRANDGUARD_E2E_DATA_DIR = dataDir;
const port = Number(process.env.BRANDGUARD_E2E_PORT || 8172);
const python = process.platform === "win32"
  ? path.join(repoRoot, ".venv", "Scripts", "python.exe")
  : path.join(repoRoot, ".venv", "bin", "python");
const sqlitePath = path.join(dataDir, "e2e.sqlite3").replaceAll("\\", "/");

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 240_000,
  expect: { timeout: 120_000 },
  workers: 1,
  reporter: "list",
  globalTeardown: "./tests/e2e/cleanup.mjs",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    browserName: "chromium",
    launchOptions: { channel: "chrome" },
    headless: true,
    trace: "retain-on-failure",
  },
  webServer: {
    command: `"${python}" scripts/run_local.py --port ${port}`,
    cwd: repoRoot,
    url: `http://127.0.0.1:${port}`,
    timeout: 180_000,
    reuseExistingServer: false,
    env: {
      ENVIRONMENT: "development",
      DATABASE_URL: `sqlite:///${sqlitePath}`,
      DEMO_MODE: "true",
      LLM_PROVIDER: "mock",
      CHROMA_PERSIST_DIR: path.join(dataDir, "chroma"),
      ASSET_STORAGE_DIR: path.join(dataDir, "uploads"),
      EMBEDDING_MODEL_PATH: path.join(dataDir, "no-model"),
      IMAGE_REVIEW_ENABLED: "false",
      PYTHONPATH: repoRoot,
    },
  },
});
