import { expect, test, type Page } from "@playwright/test";

/**
 * Phase 1 acceptance flow (mock inference):
 * create match -> HLS URL -> live dashboard -> start -> video -> mocked ball
 * movement -> events over WebSocket -> JSON inspector -> mini pitch -> stop/restart.
 */
const HLS_URL = process.env.E2E_HLS_URL ?? "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8";

async function overlayHasPixels(page: Page): Promise<boolean> {
  return page.locator("canvas").first().evaluate((canvas: HTMLCanvasElement) => {
    const ctx = canvas.getContext("2d");
    if (!ctx || canvas.width === 0) return false;
    const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
    for (let i = 3; i < data.length; i += 4) if (data[i] > 0) return true;
    return false;
  });
}

async function ballPosition(page: Page): Promise<string | null> {
  const ball = page.locator("svg[aria-label^='Mini pitch'] circle.fill-yellow-300");
  if ((await ball.count()) === 0) return null;
  return `${await ball.getAttribute("cx")},${await ball.getAttribute("cy")}`;
}

test("phase 1: create, process, inspect, stop and restart a match", async ({ page }) => {
  const suffix = Date.now().toString().slice(-5);

  // 1-2. Create a match with an HLS URL.
  await page.goto("/matches/new");
  await page.getByPlaceholder("Arsenal vs Chelsea").fill(`E2E ${suffix}`);
  await page.getByPlaceholder("Arsenal", { exact: true }).fill(`Home ${suffix}`);
  await page.getByPlaceholder("Chelsea", { exact: true }).fill(`Away ${suffix}`);
  await page.getByPlaceholder("Premier League").fill("E2E League");
  await page.getByPlaceholder("https://example.com/live-match.m3u8").fill(HLS_URL);

  // 3-4. Create & start, which opens the processing dashboard.
  await page.getByRole("button", { name: "Create & start processing" }).click();
  await expect(page).toHaveURL(/\/matches\/match_[a-z0-9]+\/live$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(`Home ${suffix}`);
  await expect(page.getByText("Processing", { exact: true }).first()).toBeVisible();

  // 5. The video element is attached to the source.
  await expect(page.locator("video")).toHaveCount(1);

  // 6. Mocked ball/player detections are drawn on the overlay.
  await expect.poll(() => overlayHasPixels(page)).toBe(true);

  // 7. Events stream in over the WebSocket.
  const feed = page.getByRole("region", { name: "Live events" });
  await expect(feed.locator("button[aria-pressed]").first()).toBeVisible();

  // 8. Clicking an event shows its full JSON.
  const firstEvent = feed.locator("button[aria-pressed]").first();
  await firstEvent.click();
  const inspector = page.getByRole("region", { name: "JSON inspector" });
  await expect(inspector).toContainText('"event_id"');
  await expect(inspector).toContainText('"match_clock"');

  // 9. The mini pitch ball moves.
  await expect.poll(() => ballPosition(page)).not.toBeNull();
  const before = await ballPosition(page);
  await expect.poll(() => ballPosition(page), { timeout: 15_000 }).not.toBe(before);

  // 10. Stop, then restart.
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Restart", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Restart" }).click();
  await expect(page.getByText("Processing", { exact: true }).first()).toBeVisible();
  await expect(feed.locator("button[aria-pressed]").first()).toBeVisible();

  // Leave the system idle.
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible();
});

test("validation errors are shown inline", async ({ page }) => {
  await page.goto("/matches/new");
  await page.getByPlaceholder("https://example.com/live-match.m3u8").fill("ftp://not-allowed");
  await page.getByRole("button", { name: "Create match" }).click();
  await expect(page.getByText("Match name is required")).toBeVisible();
  await expect(page.getByText("URL must start with http:// or https://")).toBeVisible();
});
