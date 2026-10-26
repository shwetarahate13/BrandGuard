const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../src/onboarding.ts"), "utf8");
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;

function loadOnboarding() {
  const module = { exports: {} };
  vm.runInNewContext(javascript, { exports: module.exports, module });
  return module.exports;
}

test("onboarding dismissal is saved per account and role", () => {
  const onboarding = loadOnboarding();
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };

  assert.equal(onboarding.hasSeenOnboarding("user one", "creator", storage), false);
  onboarding.markOnboardingSeen("user one", "creator", storage);
  assert.equal(onboarding.hasSeenOnboarding("user one", "creator", storage), true);
  assert.equal(onboarding.hasSeenOnboarding("user two", "creator", storage), false);
  assert.equal(onboarding.hasSeenOnboarding("user one", "manager", storage), false);
});

test("role tips explain each role's allowed workflow", () => {
  const sourceText = fs.readFileSync(path.join(__dirname, "../src/components/OnboardingTips.tsx"), "utf8");
  assert.match(sourceText, /Start with a content check/);
  assert.match(sourceText, /Manage the approval queue/);
  assert.match(sourceText, /Review assigned content/);
  assert.match(sourceText, /Set up and monitor the workspace/);
  assert.match(sourceText, /High-risk content needs an assigned reviewer/);
  assert.match(sourceText, /Admins can manage the system but do not approve submissions/);
});
