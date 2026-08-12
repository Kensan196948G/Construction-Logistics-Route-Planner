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

await test("levelMeta maps the backend exclusion_consideration level", () => {
  const c = new Component();
  assert.equal(c.levelMeta("exclusion_consideration").label, "除外検討");
});

await test("_geoInv inverts _geo", () => {
  const c = new Component();
  const [x, y] = c._geoInv(35.65, 139.75);
  const [lat, lng] = c._geo(x, y);
  assert.ok(Math.abs(lat - 35.65) < 1e-9, "latitude round-trip");
  assert.ok(Math.abs(lng - 139.75) < 1e-9, "longitude round-trip");
});

await test("confirmRisk posts status with the configured API key", async () => {
  let captured;
  const { Component: C } = loadComponent({
    fetch: (url, opts) => {
      captured = { url, opts };
      return Promise.resolve({ ok: true, json: async () => ({ status: "confirmed" }) });
    },
  });
  const c = new C();
  c.state = Object.assign({}, c.state, { apiKey: "test-key-123", riskComment: "現地確認済み" });
  await c.confirmRisk("route-1", "risk-1", "confirmed");
  assert.equal(captured.url, "/api/routes/route-1/risks/risk-1/confirm");
  assert.equal(captured.opts.headers.Authorization, "Bearer test-key-123");
  const body = JSON.parse(captured.opts.body);
  assert.equal(body.status, "confirmed");
  assert.equal(body.comment, "現地確認済み");
});

await test("testApi verifies the key against /api/me", async () => {
  let capturedUrl;
  const { Component: C } = loadComponent({
    fetch: (url) => {
      capturedUrl = url;
      return Promise.resolve({ ok: true });
    },
  });
  const c = new C();
  c.state = Object.assign({}, c.state, { apiKey: "test-key-123" });
  await c.testApi();
  assert.equal(capturedUrl, "/api/me");
  assert.equal(c.state.apiStatus, "ok");
});

await test("downloadReport without a selected project shows a clear error", async () => {
  const { Component: C } = loadComponent({ fetch: () => Promise.resolve({ ok: true }) });
  const c = new C();
  c.state = Object.assign({}, c.state, { activeProjectId: null });
  await c.downloadReport("markdown");
  assert.ok(c.state.apiError.includes("案件を選択"), "must tell the user to select a project");
});

await test("createProject posts delivery, avoid, vehicle and owner fields", async () => {
  const posts = [];
  const { Component: C } = loadComponent({
    fetch: (url, opts) => {
      if (opts && opts.method === "POST") posts.push({ url, opts });
      return Promise.resolve({ ok: true, json: async () => ({ id: "prj_created" }) });
    },
  });
  const c = new C();
  c.state = Object.assign({}, c.state, {
    apiKey: "test-key-123",
    timeWindow: "morning_peak",
    nightAllowed: true,
    avoid: { school: true, residential: false, crossing: true, slope: false, narrow: false },
    projectForm: {
      project_name: "検証工事", site_name: "検証現場", planner: "qa",
      start_name: "出発地", start_lat: "35.68", start_lng: "139.76",
      dest_name: "到着地", dest_lat: "35.65", dest_lng: "139.74",
      length_m: "12.0", width_m: "2.5", height_m: "3.8", gross_weight_t: "28.0",
      axle_weight_t: "10.0", cargo_type: "PCa部材", special_vehicle: true,
      delivery_date: "2026-09-01", notes: "テスト", time_window: "daytime"
    },
    clientType: "public"
  });
  const created = await c.createProject();
  assert.equal(created.id, "prj_created");
  const post = posts.find(p=>p.url === "/api/projects");
  assert.ok(post, "create POST must be issued");
  assert.equal(post.opts.headers.Authorization, "Bearer test-key-123");
  const body = JSON.parse(post.opts.body);
  assert.equal(body.delivery.time_window, "morning_peak");
  assert.equal(body.delivery.night_delivery_allowed, true);
  assert.deepEqual(body.avoid_conditions, ["schools", "rail_crossings"]);
  assert.equal(body.vehicle.special_vehicle_flag, true);
  assert.equal(body.owner_type, "public");
  assert.equal(body.vehicle.gross_weight_t, 28.0);
});

await test("saveAndGenerate creates the project then generates and evaluates routes", async () => {
  const calls = [];
  const { Component: C } = loadComponent({
    fetch: (url, opts) => {
      calls.push(url);
      if (url === "/api/projects" && opts && opts.method === "POST") {
        return Promise.resolve({ ok: true, json: async () => ({ id: "prj_1" }) });
      }
      if (url === "/api/projects/prj_1/routes/generate") {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            routes: [
              { id: "r1", route_type: "shortest", name: "候補A", distance_km: 1.2, duration_min: 5, risk_level: "pending", risk_score: 0, geometry: [] },
            ],
          }),
        });
      }
      if (url === "/api/routes/r1/evaluate") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ risk_level: "caution", risk_score: 10, summary: "評価済み", risk_counts: { caution: 1 }, risks: [] }),
        });
      }
      if (url === "/api/projects") {
        return Promise.resolve({ ok: true, json: async () => [] });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    },
  });
  const c = new C();
  c.state = Object.assign({}, c.state, {
    projectForm: Object.assign({}, c.state.projectForm, {
      project_name: "検証工事", site_name: "現場", planner: "qa",
      start_name: "出発", dest_name: "到着"
    })
  });
  await c.saveAndGenerate();
  assert.ok(calls.includes("/api/projects/prj_1/routes/generate"), "route generation must be called");
  assert.ok(calls.includes("/api/routes/r1/evaluate"), "evaluation must be called for each route");
  assert.equal(c.state.activeProjectId, "prj_1");
  assert.ok(c.state.apiRoutes && c.state.apiRoutes.length === 1);
  assert.equal(c.state.screen, "routes");
});

await test("submitProject posts a review request for the active project", async () => {
  const posts = [];
  const { Component: C } = loadComponent({
    fetch: (url, opts) => {
      if (opts && opts.method === "POST") posts.push({ url, opts });
      if (url === "/api/projects") return Promise.resolve({ ok: true, json: async () => [] });
      return Promise.resolve({ ok: true, json: async () => ({ status: "review_required" }) });
    },
  });
  const c = new C();
  c.state = Object.assign({}, c.state, { activeProjectId: "prj_9", apiKey: "test-key-123" });
  await c.submitProject();
  const post = posts.find(p=>p.url === "/api/projects/prj_9/submit");
  assert.ok(post, "submit POST must be issued");
  assert.equal(post.opts.method, "POST");
  assert.equal(post.opts.headers.Authorization, "Bearer test-key-123");
  assert.ok(c.state.apiNotice.includes("レビュー依頼"), "success notice must be shown");
});

if (process.exitCode) {
  console.error(`\n${passed} passed, with failures.`);
} else {
  console.log(`\n${passed} passed`);
}
