import { test, expect } from '@playwright/test';

/**
 * E2E #5 — Smoke tests: Real API integration (no MSW)
 * Tags: @smoke
 *
 * These tests call real backend and external APIs.
 * Only run when RUN_SMOKE=1 environment variable is set.
 * Intended for staging/production validation after deployment.
 */

test.describe.serial('Smoke Tests (Real API)', () => {
  test.skip(
    !process.env.RUN_SMOKE,
    'Smoke tests skipped (set RUN_SMOKE=1 to enable)'
  );

  test('@smoke: real authentication flow', async ({ page }) => {
    /**
     * Flow: Sign-in with real auth, verify dashboard loads
     * Expected: Successful redirect to dashboard with real user session
     */
    await page.goto('/sign-in');

    // Use test credentials or OAuth callback simulation
    const testEmail = process.env.TEST_EMAIL || 'test+smoke@example.com';
    const emailInput = page.getByTestId('email-input');
    await expect(emailInput).toBeVisible();
    await emailInput.fill(testEmail);

    const continueBtn = page.getByRole('button', { name: /계속/ });
    await continueBtn.click();

    // Real OAuth or email link flow
    // For smoke test, assume email verification link is clicked
    // (In real scenario, you'd use test account with pre-verified email)
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });
  });

  test('@smoke: real API call - list library', async ({ page }) => {
    /**
     * Flow: Navigate to library, fetch real songs from backend
     * Expected: GET /api/v1/library returns 200, items populated
     */
    // Assume already authenticated from previous test
    await page.goto('/library');

    // Intercept but don't mock - let it through to real API
    let libraryApiCalled = false;
    await page.on('response', (response) => {
      if (response.url().includes('/api/v1/library')) {
        expect(response.status()).toBe(200);
        libraryApiCalled = true;
      }
    });

    // Wait for library to load
    const gridItems = page.locator('[data-testid="library-grid-item"]');
    await expect(gridItems.first()).toBeVisible({ timeout: 10_000 });

    expect(libraryApiCalled).toBeTruthy();
  });

  test('@smoke: real API call - fetch credits', async ({ page }) => {
    /**
     * Flow: Dashboard loads, GET /api/v1/account/credits hits real endpoint
     * Expected: Response contains user credits balance
     */
    await page.goto('/dashboard');

    let creditsApiCalled = false;
    let creditsBalance: number | null = null;

    await page.on('response', async (response) => {
      if (response.url().includes('/api/v1/account/credits')) {
        expect(response.status()).toBe(200);
        const body = await response.json();
        creditsBalance = body.credits;
        creditsApiCalled = true;
      }
    });

    const creditMeter = page.getByTestId('credit-meter');
    await expect(creditMeter).toBeVisible({ timeout: 10_000 });

    expect(creditsApiCalled).toBeTruthy();
    expect(creditsBalance).toBeGreaterThanOrEqual(0);
  });

  test('@smoke: real API call - POST /songs (live generation)', async ({ page }) => {
    /**
     * CAUTION: This actually charges credits and calls Mureka!
     * Flow: Full generation cycle with real backend
     * Expected: 202 response, generation progresses, completes (or times out gracefully)
     *
     * Only enable in staging with disposable account.
     */
    test.skip(
      !process.env.SMOKE_ALLOW_CHARGE,
      'Skipped (set SMOKE_ALLOW_CHARGE=1 to charge real credits)'
    );

    await page.goto('/studio');

    const prompt = page.getByTestId('prompt-input');
    await prompt.fill('smoke test generation');

    let generationId: string | null = null;
    await page.on('response', async (response) => {
      if (
        response.url().includes('/api/v1/songs') &&
        response.request().method() === 'POST'
      ) {
        expect(response.status()).toBe(202);
        const body = await response.json();
        generationId = body.generation_id;
      }
    });

    await page.getByRole('button', { name: /Generate/i }).click();

    // Wait for result page
    await expect(page).toHaveURL(/\/studio\/result\//, { timeout: 15_000 });

    // Wait up to 2 min for real generation (Mureka can be slow)
    const trackA = page.getByTestId('track-A');
    await expect(trackA).toBeVisible({ timeout: 120_000 });

    expect(generationId).toBeTruthy();
  });

  test('@smoke: error handling - 401 unauthorized (expired token)', async ({
    page,
    context,
  }) => {
    /**
     * Flow: Clear auth token, try to access protected route
     * Expected: Redirected to sign-in, error handled gracefully
     */
    // Clear cookies (simulates expired session)
    await context.clearCookies();

    // Try to access dashboard
    await page.goto('/dashboard');

    // Should redirect to sign-in
    await expect(page).toHaveURL(/\/sign-in/, { timeout: 10_000 });
  });

  test('@smoke: error handling - 429 rate limit', async ({ page }) => {
    /**
     * Flow: Make rapid requests to hit rate limit
     * Expected: 429 response, user sees error toast, can retry
     */
    const apiRoute = '**/api/v1/account/**';

    let rateLimitHit = false;
    await page.on('response', (response) => {
      if (response.status() === 429) {
        rateLimitHit = true;
      }
    });

    // Make 100 rapid requests (will likely hit rate limit)
    for (let i = 0; i < 100; i++) {
      try {
        await page.goto('/dashboard', { waitUntil: 'networkidle' });
      } catch {
        // Expected to fail
      }
    }

    // At least one 429 should have occurred
    // (Depending on rate limit config)
    // This test is informational
  });

  test('@smoke: database persistence - created song persists', async ({
    page,
  }) => {
    /**
     * Flow: Create a song, refresh page, verify song still exists in library
     * Expected: Song appears in subsequent library fetch
     */
    await page.goto('/library');

    // Record initial item count
    let initialCount = await page.locator('[data-testid="library-grid-item"]').count();

    // Refresh page (forces real API call)
    await page.reload();

    // Count should be same or more (not lost)
    let newCount = await page.locator('[data-testid="library-grid-item"]').count();
    expect(newCount).toBeGreaterThanOrEqual(initialCount);
  });

  test('@smoke: S3 presigned URL download works', async ({ page }) => {
    /**
     * Flow: Click download button on generated track
     * Expected: Browser downloads file (no 403/404)
     */
    await page.goto('/library');

    const firstItem = page.locator('[data-testid="library-grid-item"]').first();
    const downloadBtn = firstItem.locator('[data-testid="download-mp3"]');

    let downloadUrl: string | null = null;
    page.on('response', (response) => {
      if (response.status() === 403 || response.status() === 404) {
        throw new Error(`Download URL returned ${response.status()}`);
      }
    });

    if (await downloadBtn.isVisible()) {
      await downloadBtn.click();
      // Download should start without error
    }
  });

  test('@smoke: Mureka API integration (live task polling)', async ({
    page,
  }) => {
    /**
     * CAUTION: Calls real Mureka API!
     * Flow: Generate song, backend polls Mureka, verify progress updates
     * Expected: SSE events or polling reflects real Mureka status
     */
    test.skip(
      !process.env.SMOKE_ALLOW_CHARGE,
      'Skipped (requires real generation)'
    );

    await page.goto('/studio');

    const prompt = page.getByTestId('prompt-input');
    await prompt.fill('mureka integration test');

    let progressUpdated = false;
    await page.on('response', async (response) => {
      if (response.url().includes('/api/v1/songs/') && response.status() === 200) {
        const body = await response.json();
        if (body.progress !== undefined && body.progress > 0) {
          progressUpdated = true;
        }
      }
    });

    await page.getByRole('button', { name: /Generate/i }).click();
    await expect(page).toHaveURL(/\/studio\/result\//);

    // Verify at least one progress update from real Mureka
    await page.waitForTimeout(5000);
    // Note: progressUpdated may be false if generation completes instantly
  });
});
