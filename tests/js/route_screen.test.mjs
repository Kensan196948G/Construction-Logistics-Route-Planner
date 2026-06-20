// Behavioral tests for the route-screen logic in app/static/component.js.
//
// component.js is a browser global script (`class Component extends DCLogic`),
// not a module, and Chromium exits immediately (SIGTRAP) in this environment.
// We therefore load it into a Node `vm` sandbox with stubbed globals (DCLogic,
// Leaflet `L`, and a controllable `fetch`) and exercise the pure logic directly.
//
// Run: node tests/js/route_screen.test.mjs

import vm from "node:vm";
import fs from "node:fs";
import assert from "node:assert/strict";

const src = fs.readFileSync(new URL("../../app/static/component.js", import.meta.url), "utf8");

// Faithful-enough DCLogic base: setState merges a patch and runs the callback,
// but skips the real DOM re-render (no template mounted in this harness).
class DCLogic {
  constructor() {
    this._kept = {};
  }
  setState(updater, cb) {
    const patch = typeof updater === "function" ? updater(this.state) : updater;
    this.state = Object.assign({}, this.state, patch);
    if (typeof cb === "function") cb();
  }
  renderVals() {
    return {};
  }
}

function loadComponent(extraGlobals = {}) {
  const sandbox = {
    DCLogic,
    L: { marker: () => ({ bindPopup: () => ({ addTo: () => ({}) }), on: () => ({}) }) },
    console,
    JSON,
    Math,
    Array,
    Object,
    String,
    Number,
    Boolean,
    Promise,
    setTimeout,
    ...extraGlobals,
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(src + "\n;this.__Component = Component;", sandbox);
  return { Component: sandbox.__Component, sandbox };
}

let passed = 0;
function test(name, fn) {
  return Promise.resolve()
    .then(fn)
    .then(() => {
      passed += 1;
      console.log(`  ok - ${name}`);
    })
    .catch((err) => {
      console.error(`  FAIL - ${name}\n    ${err.message}`);
      process.exitCode = 1;
    });
}

const { Component } = loadComponent();

await test("_geo projects SVG coords into the demo bounding box", () => {
  const c = new Component();
  const [lat, lng] = c._geo(110, 650);
  assert.ok(lat <= 35.69 && lat >= 35.63, `lat ${lat} out of box`);
  assert.ok(lng >= 139.72 && lng <= 139.8, `lng ${lng} out of box`);
});

await test("_geo is monotonic: +y -> south (lower lat), +x -> east (higher lng)", () => {
  const c = new Component();
  const [latTop] = c._geo(500, 100);
  const [latBottom] = c._geo(500, 700);
  const [, lngWest] = c._geo(100, 400);
  const [, lngEast] = c._geo(900, 400);
  assert.ok(latTop > latBottom, "higher y must yield lower latitude");
  assert.ok(lngEast > lngWest, "higher x must yield higher longitude");
});

await test("regression: the old detail-panel formula diverged from _geo", () => {
  // The pre-fix detail panel used coords:(35.62 - y*0.00014, 139.71 + x*0.00016),
  // which is a different projection than the map markers' _geo(). Confirm the
  // old formula really disagreed (so the fix is not a no-op) and that _geo is now
  // the single source the panel must use.
  const c = new Component();
  const x = 640;
  const y = 300;
  const [geoLat, geoLng] = c._geo(x, y);
  const oldLat = 35.62 - y * 0.00014;
  const oldLng = 139.71 + x * 0.00016;
  assert.ok(Math.abs(geoLat - oldLat) > 0.01, "old lat should differ from _geo by >0.01deg");
  assert.ok(Math.abs(geoLng - oldLng) > 0.01, "old lng should differ from _geo by >0.01deg");
});

await test("runKnowledgeSearch applies a fresh result", async () => {
  let resolveFetch;
  const { Component: C, sandbox } = loadComponent({
    fetch: () =>
      new Promise((res) => {
        resolveFetch = () =>
          res({ ok: true, json: async () => ({ answer: "BRIDGE ANSWER", confirmation_targets: ["確認先A"] }) });
      }),
  });
  const c = new C();
  c.state = Object.assign({}, c.state, { kQuery: "橋梁" });
  const p = c.runKnowledgeSearch();
  resolveFetch();
  await p;
  assert.ok(c.state.kAnswer.includes("BRIDGE ANSWER"), "answer should be applied");
  assert.ok(c.state.kAnswer.includes("確認先A"), "confirmation targets should be appended");
  assert.equal(c.state.kSearching, false);
  void sandbox;
});

await test("runKnowledgeSearch drops a stale result when the query changed mid-flight", async () => {
  let resolveFetch;
  const { Component: C } = loadComponent({
    fetch: () =>
      new Promise((res) => {
        resolveFetch = () =>
          res({ ok: true, json: async () => ({ answer: "BRIDGE ANSWER", confirmation_targets: ["確認先A"] }) });
      }),
  });
  const c = new C();
  c.state = Object.assign({}, c.state, { kQuery: "橋梁" });
  const p = c.runKnowledgeSearch(); // captures q = "橋梁"
  c.state = Object.assign({}, c.state, { kQuery: "トンネル" }); // user edits mid-search
  resolveFetch();
  await p;
  assert.equal(c.state.kAnswer, "", "stale answer must not be applied to the new query");
  assert.equal(c.state.kSearching, false, "loading state must be cleared");
});

if (process.exitCode) {
  console.error(`\n${passed} passed, with failures.`);
} else {
  console.log(`\n${passed} passed`);
}
