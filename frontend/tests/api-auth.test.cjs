const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const apiSource = fs.readFileSync(path.join(__dirname, "../src/api.ts"), "utf8");
const apiJavaScript = ts.transpileModule(apiSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;

function loadApi(detail, pathname = "/login") {
  const storage = new Map();
  const requests = [];
  const location = { pathname, href: pathname };
  const module = { exports: {} };
  const context = {
    exports: module.exports,
    module,
    require: () => ({}),
    localStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    },
    window: { location },
    Headers,
    FormData,
    setTimeout,
    clearTimeout,
    fetch: async (url, options) => {
      requests.push({ url, options });
      return { status: 401, ok: false, json: async () => ({ detail }) };
    },
  };
  vm.runInNewContext(apiJavaScript, context);
  return { api: module.exports.api, setToken: module.exports.setToken, storage, requests, location };
}

test("credential 401 is shown as a login error and sends no stale token", async () => {
  const client = loadApi("Incorrect email or password");
  client.setToken("stale-token");

  await assert.rejects(
    client.api.login("person@example.test", "wrong-password"),
    (error) => error.message === "Incorrect email or password",
  );

  assert.equal(client.requests[0].options.headers.get("Authorization"), null);
  assert.equal(client.storage.get("brandguard_token"), "stale-token");
  assert.equal(client.location.href, "/login");
});

test("protected endpoint 401 still clears the token and redirects to login", async () => {
  const client = loadApi("Not authenticated", "/dashboard");
  client.setToken("expired-token");

  await assert.rejects(client.api.getMe(), /Session expired\. Please log in again\./);

  assert.equal(client.requests[0].options.headers.get("Authorization"), "Bearer expired-token");
  assert.equal(client.storage.has("brandguard_token"), false);
  assert.equal(client.location.href, "/login");
});
