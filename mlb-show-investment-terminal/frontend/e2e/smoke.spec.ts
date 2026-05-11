import { expect, test } from "@playwright/test";

async function waitForBoot(page: import("@playwright/test").Page) {
  await page.locator(".bootscreen").waitFor({ state: "detached", timeout: 5000 }).catch(() => undefined);
}

async function expectCanvasHasPixels(page: import("@playwright/test").Page) {
  await expect.poll(async () => page.locator("[data-testid='terminal-3d-canvas']").evaluate((canvas) => {
    const source = canvas as HTMLCanvasElement;
    const probe = document.createElement("canvas");
    probe.width = 96;
    probe.height = 96;
    const ctx = probe.getContext("2d");
    if (!ctx || source.width === 0 || source.height === 0) return 0;
    ctx.drawImage(source, 0, 0, probe.width, probe.height);
    const data = ctx.getImageData(0, 0, probe.width, probe.height).data;
    let active = 0;
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3] > 0 && (data[i] + data[i + 1] + data[i + 2]) > 12) active += 1;
    }
    return active;
  }), { timeout: 15_000 }).toBeGreaterThan(25);
}

test("terminal renders core tabs and health state", async ({ page }) => {
  await page.goto("/");
  await waitForBoot(page);
  await expect(page.getByRole("heading", { name: /MLB The Show 26 Investment Terminal/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /Overall/i })).toBeVisible();
  await expect(page.getByText("PYTHON QUANT OWNER")).toBeVisible();
  await expect(page.getByText("python", { exact: true })).toBeVisible();
  await expectCanvasHasPixels(page);
});

test("market scan UUID parser is usable on small screens", async ({ page }) => {
  await page.goto("/");
  await waitForBoot(page);
  await page.getByRole("button", { name: /Market Scan/i }).click();
  await page.getByPlaceholder(/Paste UUIDs/i).fill("ABCDEF0123456789ABCDEF0123456789\nabcdef0123456789abcdef0123456789\nbad-token-12345");
  await expect(page.getByText("1 valid")).toBeVisible();
  await expect(page.getByText("1 duplicates")).toBeVisible();
  await expect(page.getByText("1 invalid tokens")).toBeVisible();
});

test("all parity tabs render their primary panels", async ({ page }) => {
  await page.goto("/");
  await waitForBoot(page);
  const cases = [
    [/Overall/i, /App Health/i],
    [/Card Analysis/i, /Find Card/i],
    [/OVR Predictor/i, /Threshold Model/i],
    [/Market Scan/i, /Universe/i],
    [/Validate/i, /Manual Flip Validation/i],
    [/Method/i, /Parity Audit/i]
  ] as const;
  for (const [tab, panel] of cases) {
    await page.getByRole("button", { name: tab }).click();
    await expect(page.getByRole("heading", { name: panel })).toBeVisible();
  }
});

test("layout screenshot has no horizontal overflow or overlapping primary controls", async ({ page }) => {
  await page.goto("/");
  await waitForBoot(page);
  await page.getByRole("button", { name: /Market Scan/i }).click();
  await page.getByPlaceholder(/Paste UUIDs/i).fill("ABCDEF0123456789ABCDEF0123456789");
  const screenshot = await page.screenshot({ fullPage: true });
  expect(screenshot.length).toBeGreaterThan(10_000);
  const metrics = await page.evaluate(() => {
    const tabs = document.querySelector(".tabs")?.getBoundingClientRect();
    const main = document.querySelector("main")?.getBoundingClientRect();
    return {
      overflow: document.documentElement.scrollWidth - window.innerWidth,
      separated: tabs && main ? tabs.bottom <= main.top + 1 : false
    };
  });
  expect(metrics.overflow).toBeLessThanOrEqual(1);
  expect(metrics.separated).toBeTruthy();
});

test("mock market scan renders final decision, rarity, and separated EV columns", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  const uuid = "abcdef0123456789abcdef0123456789";
  const result: any = {
    uuid_parse: { uuids: [uuid], duplicates: [], invalid_tokens: [], raw_count: 1 },
    mode: "paste_uuids",
    records: [{
      uuid,
      name: "Gold Fixture",
      rarity: "Gold",
      card: { uuid, name: "Gold Fixture", rarity: "Gold", current_ovr: 83 },
      raw_bid: 1000,
      raw_ask: 1200,
      after_tax_sale: 1080,
      flip_profit: 80,
      flip_roi: 0.08,
      forecast_ev_7d: -0.18,
      forecast_direction: "FORECAST BEARISH",
      validation_tier: "BRONZE",
      decision_action: "BUY FLIP",
      responsible_channel: "flip",
      decision_reason_codes: "EXECUTABLE_FLIP_EDGE,POSITIVE_AFTER_TAX_EDGE",
      decision_blockers: "calibration_present",
      flip: { action: "BUY", sell_price: 1200, buy_price: 1000, after_tax_sale: 1080, profit: 80, roi: 0.08, reason_codes: ["POSITIVE_AFTER_TAX_EDGE"] },
      upgrade: { action: "HOLD", current_ovr: 83, rarity: "Gold", probability_kind: "scenario" },
      forecast: {
        status: "ok",
        diagnostic_only: true,
        direction: "FORECAST BEARISH",
        expected_ret: -0.18,
        tier: "BRONZE",
        formula: { return_formula: "((terminal_price * spread_ratio * (1 - tax_rate)) - current_price) / current_price" },
      },
      decision: {
        action: "BUY FLIP",
        responsible_channel: "flip",
        reason_codes: ["EXECUTABLE_FLIP_EDGE", "POSITIVE_AFTER_TAX_EDGE"],
        blockers: ["calibration_present"],
        formula_inputs: { sell_price: 1200, buy_price: 1000, after_tax_sale: 1080, profit: 80, roi: 0.08 },
        model_status: "uncalibrated_threshold_model,forecast_diagnostic_only",
        probability_kind: "scenario",
        explanation: "Executable bid/ask math clears price, ROI, and liquidity gates.",
      },
    }],
    partitions: { flip_buys: [], upgrade_buys: [], watch: [], holds: [], sells: [], no_trade: [], observational: [], dropped: [] },
    counts: { flip_buys: 0, upgrade_buys: 0, watch: 0, holds: 0, sells: 0, no_trade: 0, observational: 0, dropped: 0 },
    progress: { total: 1, completed: 1, status: "complete", elapsed_seconds: 0.01, rate_limit_message: "mock" },
    tier_distribution: { BRONZE: 1 },
    rarity_distribution: { Gold: 1 },
    market_health: { median_spread: 0.166, median_liquidity_recent: 10, cards_with_forecast_warnings: 1, cards_with_positive_flip_roi: 1 },
    dropped_summary: {},
  };
  result.partitions.flip_buys = result.records;
  result.counts.flip_buys = 1;

  await page.route("**/api/scan/jobs", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ job_id: "mock-job", status: "queued", total: 1, completed: 0, dropped_count: 0, invalid_count: 0, started_at: "2026-05-11T00:00:00Z", updated_at: "2026-05-11T00:00:00Z" }),
  }));
  await page.route("**/api/scan/jobs/mock-job", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ job_id: "mock-job", status: "complete", total: 1, completed: 1, dropped_count: 0, invalid_count: 0, started_at: "2026-05-11T00:00:00Z", updated_at: "2026-05-11T00:00:00Z", result }),
  }));

  await page.goto("/");
  await waitForBoot(page);
  await page.getByRole("button", { name: /Market Scan/i }).click();
  await page.getByPlaceholder(/Paste UUIDs/i).fill(uuid);
  await page.getByRole("button", { name: /Run scan/i }).click();
  await expect(page.getByRole("heading", { name: "Flip Buys" })).toBeVisible();
  await expect(page.getByText("Gold Fixture").first()).toBeVisible();
  await expect(page.getByText("BUY FLIP").first()).toBeVisible();
  await expect(page.getByText("Gold").first()).toBeVisible();
  await expect(page.getByText("Flip ROI").first()).toBeVisible();
  await expect(page.getByText("Forecast EV").first()).toBeVisible();
  expect(consoleErrors).toEqual([]);
});
