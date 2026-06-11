import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function waitForBoot(page: import("@playwright/test").Page) {
  await page.locator(".bootscreen").waitFor({ state: "detached", timeout: 5000 }).catch(() => undefined);
}

async function expectBackdropVisible(page: import("@playwright/test").Page) {
  const backdrop = page.getByTestId("terminal-backdrop");
  await expect(backdrop).toBeVisible();
  const box = await backdrop.boundingBox();
  expect(box?.width ?? 0).toBeGreaterThan(300);
  expect(box?.height ?? 0).toBeGreaterThan(300);
}

async function openTerminalTab(page: import("@playwright/test").Page, label: RegExp, value: string) {
  const button = page.getByRole("button", { name: label }).first();
  if (await button.count() && await button.isVisible()) {
    await button.click();
    return;
  }
  await page.getByLabel("Terminal section").selectOption(value);
}

test("terminal renders core tabs and health state", async ({ page }) => {
  await page.goto("/");
  await waitForBoot(page);
  await expect(page.getByRole("heading", { name: /MLB The Show 26 Investment Terminal/i })).toBeVisible();
  const commandButton = page.getByRole("button", { name: /Command Center/i }).first();
  if (await commandButton.isVisible()) {
    await expect(commandButton).toBeVisible();
  } else {
    await expect(page.getByLabel("Terminal section")).toBeVisible();
  }
  await expect(page.getByText("PYTHON QUANT OWNER")).toBeVisible();
  await expect(page.getByText("python", { exact: true })).toBeVisible();
  await expectBackdropVisible(page);
});

test("command center has no critical automated accessibility violations", async ({ page }) => {
  await page.goto("/");
  await waitForBoot(page);
  const results = await new AxeBuilder({ page })
    .disableRules(["color-contrast"])
    .analyze();
  const severe = results.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  expect(severe).toEqual([]);
});

test("market scan UUID parser is usable on small screens", async ({ page }) => {
  await page.goto("/");
  await waitForBoot(page);
  await openTerminalTab(page, /Market Scanner/i, "scanner");
  await page.getByPlaceholder(/Paste UUIDs/i).fill("ABCDEF0123456789ABCDEF0123456789\nabcdef0123456789abcdef0123456789\nbad-token-12345");
  await expect(page.getByText("1 valid")).toBeVisible();
  await expect(page.getByText("1 duplicates")).toBeVisible();
  await expect(page.getByText("1 invalid tokens")).toBeVisible();
});

test("all parity tabs render their primary panels", async ({ page }) => {
  await page.goto("/");
  await waitForBoot(page);
  const cases = [
    [/Command Center/i, "command", /App Health/i],
    [/Market Scanner/i, "scanner", /Universe/i],
    [/Trade Ticket/i, "target", /Find Card/i],
    [/Strategy Matrix/i, "matrix", /Strategy Matrix/i],
    [/Forecast Lab/i, "forecast", /Forecast Lab/i],
    [/Validation/i, "validation", /Manual Flip Validation/i],
    [/Execution Ledger/i, "ledger", /Manual Trade Logging/i],
    [/Risk Inventory/i, "risk", /Inventory Quality/i],
    [/Data Audit/i, "audit", /Data Provenance/i],
    [/Operations/i, "ops", /Parity Audit/i]
  ] as const;
  for (const [tab, value, panel] of cases) {
    await openTerminalTab(page, tab, value);
    await expect(page.getByRole("main").getByRole("heading", { name: panel })).toBeVisible({ timeout: 10_000 });
  }
});

test("layout screenshot has no horizontal overflow or overlapping primary controls", async ({ page }) => {
  await page.goto("/");
  await waitForBoot(page);
  await openTerminalTab(page, /Market Scanner/i, "scanner");
  await page.getByPlaceholder(/Paste UUIDs/i).fill("ABCDEF0123456789ABCDEF0123456789");
  const screenshot = await page.screenshot({ fullPage: true });
  expect(screenshot.length).toBeGreaterThan(10_000);
  const metrics = await page.evaluate(() => {
    const nav = (document.querySelector(".tabs")?.getBoundingClientRect().height ?? 0) > 0
      ? document.querySelector(".tabs")?.getBoundingClientRect()
      : document.querySelector(".mobile-tab-select")?.getBoundingClientRect();
    const main = document.querySelector("main")?.getBoundingClientRect();
    return {
      overflow: document.documentElement.scrollWidth - window.innerWidth,
      separated: nav && main ? nav.bottom <= main.top + 1 : false
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
      decision_action: "INSTANT FLIP ONLY",
      responsible_channel: "flip",
      decision_reason_codes: "FLIP_PASS,BEARISH,HIGH_LIQUIDITY,INSTANT_FLIP_ONLY",
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
      strategy: {
        rule_version: "strategy-matrix-2026-05-13",
        flip: { verdict: "FLIP PASS", expected_net_stubs: 80, expected_roi_after_tax_and_friction: 0.08, p_successful_exit: 0.9 },
        directional: { verdict: "BEARISH", expected_return_by_horizon: { "7d": -0.18 }, p_profit: 0, validation_tier: "BRONZE" },
        inventory: { verdict: "HIGH LIQUIDITY", inventory_risk_score: 0.18 },
        composite: {
          final_action: "INSTANT FLIP ONLY",
          strategy_type: "flip",
          hold_duration: "manual_review",
          holding_instruction: "instant flip only; target exit within 2h and do not hold as an investment",
          entry_timing: "enter only as a limit buy at or below current bid; skip market buys",
          exit_timing: "after fill, immediately relist near current ask; cancel or liquidate if not exited within 2h",
          max_hold_hours: 2,
          explanation: "positive spread capture, but bearish directional forecast; do not hold as an investment"
        },
      },
      decision: {
        action: "INSTANT FLIP ONLY",
        responsible_channel: "flip",
        reason_codes: ["FLIP_PASS", "BEARISH", "INSTANT_FLIP_ONLY"],
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
  await openTerminalTab(page, /Market Scanner/i, "scanner");
  await page.getByPlaceholder(/Paste UUIDs/i).fill(uuid);
  await page.getByRole("button", { name: /Run scan/i }).click();
  await expect(page.getByRole("progressbar", { name: /Scan progress/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Flip Candidates" })).toBeVisible();
  await expect(page.getByText("Gold Fixture").first()).toBeVisible();
  await expect(page.getByText("INSTANT FLIP ONLY").first()).toBeVisible();
  await expect(page.getByText("FLIP PASS").first()).toBeVisible();
  await expect(page.getByText("BEARISH").first()).toBeVisible();
  await expect(page.getByText("Gold").first()).toBeVisible();
  await expect(page.getByText("Flip ROI").first()).toBeVisible();
  await expect(page.getByText("Forecast EV").first()).toBeVisible();
  await expect(page.getByText("Exit By").first()).toBeVisible();
  await expect(page.getByText("2h").first()).toBeVisible();
  await expect(page.getByText("INVESTABLE")).toHaveCount(0);
  expect(consoleErrors).toEqual([]);
});

test("ledger write-auth failures render as alerts without browser credentials", async ({ page }) => {
  await page.route("**/api/persistence/status", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      status: "configured",
      mode: "supabase-rest",
      server_side_writes: true,
      credential_exposure: "server-only",
      write_auth: "required",
      write_auth_configured: true
    }),
  }));
  await page.route("**/api/ledger/log", (route) => route.fulfill({
    status: 403,
    contentType: "application/json",
    body: JSON.stringify({ detail: "write token required" }),
  }));

  await page.goto("/");
  await waitForBoot(page);
  await openTerminalTab(page, /Execution Ledger/i, "ledger");
  await expect(page.getByText(/Browser clients never receive Supabase service credentials/i)).toBeVisible();
  await page.getByLabel("buy price").fill("1000");
  await page.getByLabel("sell price").fill("1200");
  await page.getByRole("button", { name: /Add local row/i }).click();
  await page.getByRole("button", { name: /Write to Supabase/i }).click();
  await expect(page.getByRole("alert")).toContainText("write token required");
});
