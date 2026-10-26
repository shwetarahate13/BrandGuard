const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../src/savedViews.ts"), "utf8");
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;

function loadSavedViews() {
  const module = { exports: {} };
  vm.runInNewContext(javascript, { exports: module.exports, module });
  return module.exports;
}

function createStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
}

test("saved views persist and are isolated by account and role", () => {
  const savedViews = loadSavedViews();
  const storage = createStorage();
  savedViews.saveDashboardView("manager-1", "manager", {
    name: "Urgent review",
    search: "spring campaign",
    statusFilter: "in_review",
  }, storage);

  const managerViews = savedViews.readSavedViews("manager-1", "manager", storage);
  assert.equal(managerViews.length, 1);
  assert.equal(managerViews[0].search, "spring campaign");
  assert.equal(managerViews[0].statusFilter, "in_review");
  assert.equal(savedViews.readSavedViews("manager-2", "manager", storage).length, 0);
  assert.equal(savedViews.readSavedViews("manager-1", "creator", storage).length, 0);
});

test("saving by name updates a view and deletion removes only the selected view", () => {
  const savedViews = loadSavedViews();
  const storage = createStorage();
  const first = savedViews.saveDashboardView("creator-1", "creator", {
    name: "Needs work", search: "", statusFilter: "changes_requested",
  }, storage)[0];
  const updated = savedViews.saveDashboardView("creator-1", "creator", {
    name: " needs work ", search: "spring", statusFilter: "all",
  }, storage);

  assert.equal(updated.length, 1);
  assert.equal(updated[0].id, first.id);
  assert.equal(updated[0].search, "spring");
  assert.equal(savedViews.deleteDashboardView("creator-1", "creator", first.id, storage).length, 0);
  assert.throws(() => savedViews.saveDashboardView("creator-1", "creator", {
    name: "  ", search: "", statusFilter: "all",
  }, storage), /Enter a name/);
});
