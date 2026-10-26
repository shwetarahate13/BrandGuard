const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../src/theme.ts"), "utf8");
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;

function loadTheme() {
  const module = { exports: {} };
  vm.runInNewContext(javascript, { exports: module.exports, module });
  return module.exports;
}

test("dark mode preference persists and applies the root class", () => {
  const theme = loadTheme();
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
  const classes = new Set();
  const root = { classList: { toggle: (name, force) => force ? classes.add(name) : classes.delete(name) } };

  assert.equal(theme.readDarkMode(storage), false);
  theme.saveDarkMode(true, storage);
  theme.applyDarkMode(theme.readDarkMode(storage), root);
  assert.equal(theme.readDarkMode(storage), true);
  assert.equal(classes.has("dark"), true);

  theme.saveDarkMode(false, storage);
  theme.applyDarkMode(theme.readDarkMode(storage), root);
  assert.equal(theme.readDarkMode(storage), false);
  assert.equal(classes.has("dark"), false);
});
