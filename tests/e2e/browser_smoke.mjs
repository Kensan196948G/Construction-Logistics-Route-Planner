// Real-browser smoke test for the MVP core flow (Firefox headless).
//
// Chromium crashes immediately in this environment (SIGTRAP), so Firefox is
// the supported browser. Run against a seeded, PoC-mode backend:
//
//   BASE_URL=http://127.0.0.1:18017 PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright node tests/e2e/browser_smoke.mjs
//
// CI boots a throwaway server + temp SQLite DB before running this file, so
// route generation and logical-delete mutations never touch real data.

import assert from "node:assert/strict";
import { firefox } from "playwright";

const BASE_URL = (process.env.BASE_URL || "http://127.0.0.1:18017").replace(/\/$/, "");

let browser;
let passed = 0;
const failures = [];

async function test(name, fn) {
  try {
    await fn();
    passed += 1;
    console.log(`  ok - ${name}`);
  } catch (err) {
    failures.push(`${name}: ${err.message}`);
    console.error(`  FAIL - ${name}\n    ${err.message}`);
  }
}

try {
  browser = await firefox.launch({ headless: true });
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const pageErrors = [];
  page.on("pageerror", (err) => pageErrors.push(String(err)));
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      // Cloudflare injects its own Web Analytics beacon on proxied hostnames;
      // our strict CSP blocks that third-party script by design. It is not a
      // page error and must not fail the smoke test.
      if (!msg.text().includes("static.cloudflareinsights.com")) pageErrors.push(msg.text());
    }
  });
  page.on("dialog", (dialog) => dialog.accept());

  await test("dashboard renders with the sample-data banner and live KPIs", async () => {
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForFunction(
      () => document.body && document.body.innerText.includes("本番利用禁止"),
      null,
      { timeout: 30000 }
    );
    await page.waitForFunction(
      () => document.body && document.body.innerText.includes("PoC（管理者）"),
      null,
      { timeout: 15000 }
    );
    const text = await page.locator("body").innerText();
    assert.ok(text.includes("登録案件"), "dashboard KPI card must be present");
    assert.ok(text.includes("PoC（管理者）"), "the PoC identity/role must be shown in the header");
    const asideBg = await page
      .locator("aside")
      .first()
      .evaluate((el) => getComputedStyle(el).backgroundColor);
    const headerBg = await page
      .locator("header")
      .first()
      .evaluate((el) => getComputedStyle(el).backgroundColor);
    assert.equal(asideBg, "rgb(255, 255, 255)", "the sidebar must use the light theme");
    assert.equal(headerBg, "rgb(255, 255, 255)", "the header must use the light theme");
  });

  await test("project search filters the list via the API", async () => {
    const input = page.locator('input[placeholder="案件名・現場名・担当者で検索"]');
    await input.fill("河川改修");
    await input.press("Enter");
    await page.waitForFunction(
      () =>
        document.body.innerText.includes("河川改修 護岸ブロック搬入") &&
        document.body.innerText.includes("1 - 1 / 全 1 件"),
      null,
      { timeout: 15000 }
    );
    const text = await page.locator("body").innerText();
    assert.ok(!text.includes("旧道拡幅"), "unrelated projects must be filtered out");
  });

  await test("opening a project generates and evaluates routes on the map screen", async () => {
    await page.getByText("河川改修 護岸ブロック搬入（架空）", { exact: true }).first().click();
    await page.waitForFunction(
      () => document.body.innerText.includes("ルート候補を生成し、リスク評価を実行しました。"),
      null,
      { timeout: 30000 }
    );
    const text = await page.locator("body").innerText();
    assert.ok(text.includes("候補"), "route candidates must be listed");
  });

  await test("knowledge search returns deterministic guidance with confirmation targets", async () => {
    await page.getByRole("button", { name: "ナレッジ検索" }).click();
    const input = page.locator('input[placeholder*="論点を入力"]');
    await input.fill("橋梁 重量制限");
    await page.getByRole("button", { name: "検索", exact: true }).click();
    await page.waitForFunction(
      () => document.body.innerText.includes("【橋梁・重量制限】"),
      null,
      { timeout: 15000 }
    );
    const text = await page.locator("body").innerText();
    assert.ok(text.includes("追加確認事項"), "confirmation targets must be listed");
  });

  await test("facilities dictionary shows seeded fictional DB points", async () => {
    await page.getByRole("button", { name: "周辺施設辞書" }).click();
    await page.waitForFunction(
      () => document.body.innerText.includes("架空大橋"),
      null,
      { timeout: 15000 }
    );
    const text = await page.locator("body").innerText();
    assert.ok(text.includes("DB 連携済み"), "the dictionary must be marked as DB-backed");
  });

  await test("admin audit log is DB-backed and exports a CSV", async () => {
    await page.getByRole("button", { name: "管理設定" }).click();
    await page.waitForFunction(
      () => /DB 連携（\d+ 件）/.test(document.body.innerText),
      null,
      { timeout: 15000 }
    );
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 20000 }),
      page.locator("button", { hasText: "CSVエクスポート" }).click(),
    ]);
    assert.ok(download.suggestedFilename().includes("audit-logs"), "audit CSV filename must be as expected");
  });

  await test("project edit updates fields through the UI", async () => {
    await page.getByRole("button", { name: "ダッシュボード" }).click();
    const input = page.locator('input[placeholder="案件名・現場名・担当者で検索"]');
    await input.fill("高架下");
    await input.press("Enter");
    await page.waitForFunction(
      () => document.body.innerText.includes("第二東名高架下"),
      null,
      { timeout: 15000 }
    );
    const row = page
      .locator("div")
      .filter({ has: page.getByText("第二東名高架下 橋梁架設資材搬入（架空）", { exact: true }) })
      .filter({ has: page.getByRole("button", { name: "編集", exact: true }) })
      .last();
    await row.getByRole("button", { name: "編集", exact: true }).click();
    await page.waitForFunction(
      () => document.body.innerText.includes("を編集中です。"),
      null,
      { timeout: 15000 }
    );
    const name = page.locator('input[placeholder="例: 第二期 護岸ブロック据付工事"]');
    await name.fill("第二東名高架下 橋梁架設資材搬入（架空・E2E編集済み）");
    await page.locator("button", { hasText: "保存のみ" }).click();
    await page.waitForFunction(
      () => document.body.innerText.includes("案件を更新しました。"),
      null,
      { timeout: 15000 }
    );
  });

  await test("logical delete archives a throwaway project", async () => {
    const uniqueName = `E2E論理削除 架空案件 ${Date.now()}`;
    const created = await page.request.post(`${BASE_URL}/api/projects`, {
      data: {
        project_name: uniqueName,
        site_name: "E2E削除ヤード",
        planner: "e2e-firefox",
        start: { name: "E2E出発", lat: 35.68, lng: 139.76 },
        destination: { name: "E2E到着", lat: 35.65, lng: 139.74 },
        vehicle: { vehicle_type: "heavy_truck", height_m: 3.8, gross_weight_t: 32 },
      },
    });
    assert.equal(created.status(), 201, `project create failed: ${await created.text()}`);
    const projectId = (await created.json()).id;

    await page.getByRole("button", { name: "ダッシュボード" }).click();
    const input = page.locator('input[placeholder="案件名・現場名・担当者で検索"]');
    await input.fill(uniqueName);
    await input.press("Enter");
    await page.waitForFunction(
      (name) => document.body.innerText.includes(name),
      uniqueName,
      { timeout: 15000 }
    );
    const row = page
      .locator("div")
      .filter({ has: page.getByText(uniqueName, { exact: true }) })
      .filter({ has: page.getByRole("button", { name: "保管", exact: true }) })
      .last();
    await row.getByRole("button", { name: "保管", exact: true }).click();
    await page.waitForFunction(
      () => document.body.innerText.includes("案件を保管（論理削除）しました。"),
      null,
      { timeout: 15000 }
    );
    const fetched = await page.request.get(`${BASE_URL}/api/projects/${projectId}`);
    assert.equal((await fetched.json()).status, "archived", "the project must be archived, not deleted");
  });

  assert.deepEqual(pageErrors, [], `no browser console/page errors expected, got: ${pageErrors.slice(0, 5).join(" | ")}`);
  await browser.close();
} catch (err) {
  failures.push(`setup: ${err.message}`);
  if (browser) await browser.close();
}

if (failures.length) {
  console.error(`\n${passed} passed, ${failures.length} failed.`);
  process.exit(1);
}
console.log(`\n${passed} passed`);
