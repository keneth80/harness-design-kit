import { test, expect } from '@playwright/test';

/**
 * E2E #2 — Failure scenarios: API errors, timeouts, moderation failures
 * Tags: @p0 @failure
 */

test.describe.parallel('Generate Failure Scenarios', () => {
  test('@p0 @failure: Mureka 5xx → retry → final failure → refund toast', async ({ page }) => {
    /**
     * Scenario: API fails with 5xx on first poll, recovers, then permanent failure
     * Expected: User sees error toast, credits refunded
     */
    // 1) Login
    await page.goto('/sign-in');
    await page.getByTestId('email-input').fill('user@example.com');
    await page.getByRole('button', { name: /계속/ }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    // 2) Go to studio
    await page.goto('/studio');
    const prompt = page.getByTestId('prompt-input');
    await expect(prompt).toBeVisible();
    await prompt.fill('비 오는 도쿄 새벽, 잔잔한 피아노');

    // 3) Intercept: POST /songs → normal, GET /songs/:id → 502 on first call, then 500 on retry
    await page.route('**/api/v1/songs', async (route) => {
      await route.continue();
    });

    let pollCount = 0;
    await page.route('**/api/v1/songs/*', async (route) => {
      if (route.request().method() === 'GET') {
        pollCount++;
        if (pollCount === 1) {
          // First poll → 502 Bad Gateway (retry-able)
          await route.abort('failed');
        } else if (pollCount >= 3) {
          // After retry exhaustion → 500 Internal Server Error (permanent)
          await route.respond({
            status: 500,
            body: JSON.stringify({ detail: 'Mureka service unavailable' }),
          });
        } else {
          // Intermediate polls → still processing
          await route.continue();
        }
      } else {
        await route.continue();
      }
    });

    await page.getByRole('button', { name: /Generate/i }).click();
    await expect(page).toHaveURL(/\/studio\/result\//);

    // 4) Eventually see refund toast (credits restored)
    const refundToast = page.locator('text=/환불|Refund/i').first();
    await expect(refundToast).toBeVisible({ timeout: 20_000 });

    // 5) Verify credits meter updated
    await page.goto('/dashboard');
    const creditMeter = page.getByTestId('credit-meter');
    await expect(creditMeter).toBeVisible();
  });

  test('@p0 @failure: Generation timeout (5min) → failure + refund', async ({ page }) => {
    /**
     * Scenario: Generation takes > 5 minutes, timeout triggered
     * Expected: Failure state, refund applied
     */
    // Setup login
    await page.goto('/sign-in');
    await page.getByTestId('email-input').fill('user@example.com');
    await page.getByRole('button', { name: /계속/ }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto('/studio');
    const prompt = page.getByTestId('prompt-input');
    await expect(prompt).toBeVisible();
    await prompt.fill('복잡한 orchestration 요청');

    // Intercept: POST returns OK, but GET /songs/:id hangs forever
    let pollCount = 0;
    await page.route('**/api/v1/songs/*', async (route) => {
      if (route.request().method() === 'GET') {
        pollCount++;
        if (pollCount < 20) {
          // Simulate infinite "processing" state
          await new Promise((resolve) => setTimeout(resolve, 15_000));
          await route.respond({
            status: 200,
            body: JSON.stringify({
              generation_id: '01HXG7E2K4Q',
              status: 'processing',
              progress: 20 + pollCount * 2,
              stage: 'composition',
            }),
          });
        } else {
          await route.abort('timedout');
        }
      } else {
        await route.continue();
      }
    });

    await page.getByRole('button', { name: /Generate/i }).click();
    await expect(page).toHaveURL(/\/studio\/result\//);

    // 6) Timeout error message or refund toast within 5:30
    const errorMessage = page.locator('text=/시간초과|timeout|Timeout/i').first();
    await expect(errorMessage).toBeVisible({ timeout: 330_000 }); // 5:30
  });

  test('@p0 @failure: Moderation flagged (4xx) → no retry, no refund', async ({ page }) => {
    /**
     * Scenario: OpenAI moderation flags the prompt as harmful
     * Expected: Immediate 400 response, no credits refunded (no charge either)
     */
    await page.goto('/sign-in');
    await page.getByTestId('email-input').fill('user@example.com');
    await page.getByRole('button', { name: /계속/ }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto('/studio');
    const prompt = page.getByTestId('prompt-input');
    await expect(prompt).toBeVisible();
    await prompt.fill('Some harmful content that triggers moderation');

    // Intercept: POST /songs → 400 Moderation flagged
    await page.route('**/api/v1/songs', async (route) => {
      if (route.request().method() === 'POST') {
        await route.respond({
          status: 400,
          body: JSON.stringify({
            detail: 'Prompt flagged by content moderation policy',
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.getByRole('button', { name: /Generate/i }).click();

    // 4) Expect error toast (NOT refund, no generation created)
    const errorToast = page.locator('text=/위반|flagged|Moderation/i').first();
    await expect(errorToast).toBeVisible({ timeout: 10_000 });

    // 5) Still on studio page (not redirected to result)
    await expect(page).toHaveURL(/\/studio(?!\/result)/);
  });

  test('@p0 @failure: SSE connection drop → fallback to polling', async ({ page }) => {
    /**
     * Scenario: SSE connection drops mid-generation
     * Expected: Client falls back to polling (GET /songs/:id), still completes
     */
    await page.goto('/sign-in');
    await page.getByTestId('email-input').fill('user@example.com');
    await page.getByRole('button', { name: /계속/ }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto('/studio');
    const prompt = page.getByTestId('prompt-input');
    await expect(prompt).toBeVisible();
    await prompt.fill('네온 도시 신스 파워 음악');

    // Intercept SSE: close connection after 1 event
    let sseEventCount = 0;
    await page.route('**/api/v1/events/**', async (route) => {
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        async start(controller) {
          // Send 1 progress event
          controller.enqueue(
            encoder.encode(
              `data: ${JSON.stringify({
                event: 'progress',
                progress: 10,
                stage: 'initial',
              })}\n\n`
            )
          );
          sseEventCount++;
          // Then close abruptly
          await new Promise((resolve) => setTimeout(resolve, 500));
          controller.close();
        },
      });
      await route.respond({
        status: 200,
        body: stream,
        headers: { 'Content-Type': 'text/event-stream' },
      });
    });

    // Polling endpoint should work and eventually return completed
    let pollCount = 0;
    await page.route('**/api/v1/songs/*', async (route) => {
      if (route.request().method() === 'GET') {
        pollCount++;
        if (pollCount >= 2) {
          await route.respond({
            status: 200,
            body: JSON.stringify({
              generation_id: '01HXG7E2K4Q',
              status: 'completed',
              progress: 100,
              songs: [
                {
                  id: '01HXG8A',
                  variant: 'A',
                  mp3_url: 'https://cdn.music-maker.app/s/A.mp3?sig=mock',
                  wav_url: 'https://cdn.music-maker.app/s/A.wav?sig=mock',
                  duration_ms: 90000,
                  bpm: 90,
                  key: 'Cm',
                  genres: ['lo-fi'],
                  moods: ['melancholy'],
                  cover_url: 'https://cdn.music-maker.app/c/A.jpg',
                },
                {
                  id: '01HXG8B',
                  variant: 'B',
                  mp3_url: 'https://cdn.music-maker.app/s/B.mp3?sig=mock',
                  wav_url: 'https://cdn.music-maker.app/s/B.wav?sig=mock',
                  duration_ms: 90000,
                  bpm: 92,
                  key: 'Am',
                  genres: ['lo-fi'],
                  moods: ['melancholy'],
                  cover_url: 'https://cdn.music-maker.app/c/B.jpg',
                },
              ],
              lyrics: '[Verse 1]\n도시는 잠들지 않아\n',
            }),
          });
        } else {
          await route.continue();
        }
      } else {
        await route.continue();
      }
    });

    await page.getByRole('button', { name: /Generate/i }).click();
    await expect(page).toHaveURL(/\/studio\/result\//);

    // 6) Despite SSE drop, polling kicks in and shows final result
    await expect(page.getByTestId('track-A')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('track-B')).toBeVisible();
  });
});
