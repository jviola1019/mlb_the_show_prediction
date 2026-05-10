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
