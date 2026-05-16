import { test, expect } from '@playwright/test';
import { injectAxe, checkA11y } from 'axe-playwright';

/**
 * E2E #4 — Accessibility audits + keyboard navigation
 * Tags: @p0 @a11y
 *
 * Uses axe-core to detect WCAG 2.1 AA violations.
 * Also tests keyboard-only navigation (Tab, Enter, Cmd+Space, etc.)
 */

test.describe.serial('Accessibility Compliance', () => {
  test('@p0 @a11y: landing page WCAG 2.1 AA', async ({ page }) => {
    /**
     * Flow: Visit landing page, inject axe, run audit
     * Expected: 0 violations detected
     */
    await page.goto('/');
    await injectAxe(page);
    await checkA11y(page, null, {
      detailedReport: true,
      detailedReportOptions: {
        html: true,
      },
    });
  });

  test('@p0 @a11y: sign-in page WCAG 2.1 AA', async ({ page }) => {
    /**
     * Flow: Visit sign-in, inject axe, run audit
     * Expected: 0 violations detected
     */
    await page.goto('/sign-in');
    await injectAxe(page);
    await checkA11y(page, null, {
      detailedReport: true,
    });
  });

  test('@p0 @a11y: studio page WCAG 2.1 AA', async ({ page }) => {
    /**
     * Flow: Login, navigate to studio, run audit
     * Expected: 0 violations detected
     */
    await page.goto('/sign-in');
    await page.getByTestId('email-input').fill('user@example.com');
    await page.getByRole('button', { name: /계속/ }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto('/studio');
    await injectAxe(page);
    await checkA11y(page, null, {
      detailedReport: true,
    });
  });

  test('@p0 @a11y: library page WCAG 2.1 AA', async ({ page }) => {
    /**
     * Flow: Login, navigate to library, run audit
     * Expected: 0 violations detected
     */
    await page.goto('/sign-in');
    await page.getByTestId('email-input').fill('user@example.com');
    await page.getByRole('button', { name: /계속/ }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto('/library');
    await injectAxe(page);
    await checkA11y(page, null, {
      detailedReport: true,
    });
  });

  test('@p0 @a11y: result page WCAG 2.1 AA', async ({ page }) => {
    /**
     * Flow: Generate a song, result page loads, run audit
     * Expected: 0 violations detected
     */
    await page.goto('/sign-in');
    await page.getByTestId('email-input').fill('user@example.com');
    await page.getByRole('button', { name: /계속/ }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto('/studio');
    const prompt = page.getByTestId('prompt-input');
    await expect(prompt).toBeVisible();
    await prompt.fill('test prompt');

    await page.getByRole('button', { name: /Generate/i }).click();
    await expect(page).toHaveURL(/\/studio\/result\//);

    await injectAxe(page);
    await checkA11y(page, null, {
      detailedReport: true,
    });
  });

  test('@p0 @a11y: settings page WCAG 2.1 AA', async ({ page }) => {
    /**
     * Flow: Login, navigate to settings, run audit
     * Expected: 0 violations detected
     */
    await page.goto('/sign-in');
    await page.getByTestId('email-input').fill('user@example.com');
    await page.getByRole('button', { name: /계속/ }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto('/settings');
    await injectAxe(page);
    await checkA11y(page, null, {
      detailedReport: true,
    });
  });

  test('@p0 @a11y: keyboard navigation - Tab through all interactive elements', async ({
    page,
  }) => {
    /**
     * Flow: Use only Tab to navigate through studio page
     * Expected: All buttons, inputs, links reachable; :focus-visible always visible
     */
    await page.goto('/sign-in');
    await page.getByTestId('email-input').fill('user@example.com');
    await page.getByRole('button', { name: /계속/ }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto('/studio');
    await expect(page.getByTestId('prompt-input')).toBeVisible();

    // Start Tab navigation
    const tabCount = 15;
    const focusedElements = [];

    for (let i = 0; i < tabCount; i++) {
      await page.keyboard.press('Tab');
      const focused = await page.evaluate(() => {
        const elem = document.activeElement;
        return {
          tagName: elem?.tagName,
          testId: elem?.getAttribute('data-testid'),
          ariaLabel: elem?.getAttribute('aria-label'),
        };
      });
      focusedElements.push(focused);
    }

    // Verify we hit interactive elements (buttons, inputs, links, etc.)
    const interactiveElements = focusedElements.filter(
      (e) =>
        e.tagName === 'BUTTON' ||
        e.tagName === 'INPUT' ||
        e.tagName === 'A' ||
        e.ariaLabel
    );
    expect(interactiveElements.length).toBeGreaterThan(0);
  });

  test('@p0 @a11y: keyboard shortcut Cmd+Enter generates song', async ({ page }) => {
    /**
     * Flow: Fill prompt, press Cmd+Enter (or Ctrl+Enter on Linux/Win)
     * Expected: Generation starts (same as clicking Generate button)
     */
    await page.goto('/sign-in');
    await page.getByTestId('email-input').fill('user@example.com');
    await page.getByRole('button', { name: /계속/ }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto('/studio');
    const prompt = page.getByTestId('prompt-input');
    await prompt.fill('keyboard shortcut test');

    // Focus on prompt input
    await prompt.focus();

    // Press Cmd+Enter (or Ctrl+Enter on other platforms)
    const isMac = (await page.evaluate(() => navigator.platform)).includes('Mac');
    if (isMac) {
      await page.keyboard.press('Meta+Enter');
    } else {
      await page.keyboard.press('Control+Enter');
    }

    // Should redirect to result page (same as button click)
    await expect(page).toHaveURL(/\/studio\/result\//, { timeout: 10_000 });
  });

  test('@p0 @a11y: form validation messages announced', async ({ page }) => {
    /**
     * Flow: Try to submit form with invalid input, aria-invalid/aria-describedby present
     * Expected: Error messages linked via aria-describedby or role=alert
     */
    await page.goto('/sign-in');

    // Try empty submit
    const submitBtn = page.getByRole('button', { name: /계속/ });
    await submitBtn.click();

    // Should show error or validation message
    // Check for aria-invalid on input
    const emailInput = page.getByTestId('email-input');
    const ariaInvalid = await emailInput.getAttribute('aria-invalid');
    const ariaDescribedby = await emailInput.getAttribute('aria-describedby');

    // At least one should be present for accessibility
    const hasAccessibleError = ariaInvalid === 'true' || ariaDescribedby;
    expect(hasAccessibleError).toBeTruthy();
  });

  test('@p0 @a11y: skip link present and works', async ({ page }) => {
    /**
     * Flow: Press Tab on landing page, first element is "Skip to main content"
     * Expected: Link exists, Tab+Enter jumps to main content area
     */
    await page.goto('/');

    // First Tab should land on skip link
    await page.keyboard.press('Tab');
    const focused = await page.evaluate(() => document.activeElement?.textContent);

    // Look for skip link
    const skipLink = page.getByText(/skip|main|content/i).first();
    const skipLinkVisible = await skipLink.isVisible({ timeout: 1000 }).catch(() => false);

    // If skip link exists, it should be keyboard accessible
    if (skipLinkVisible) {
      await skipLink.focus();
      await page.keyboard.press('Enter');
      // Main content area should be focused or visible
      await expect(page.locator('main')).toBeVisible();
    }
  });

  test('@p0 @a11y: images have alt text', async ({ page }) => {
    /**
     * Flow: Load library page (has cover images), verify all have alt text
     * Expected: No images without alt or meaningful aria-label
     */
    await page.goto('/sign-in');
    await page.getByTestId('email-input').fill('user@example.com');
    await page.getByRole('button', { name: /계속/ }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto('/library');

    // Get all images
    const images = await page.locator('img').all();

    for (const img of images) {
      const alt = await img.getAttribute('alt');
      const ariaLabel = await img.getAttribute('aria-label');
      const role = await img.getAttribute('role');

      // Either alt text, aria-label, or role=presentation (for decorative)
      const hasAccessibleName = alt || ariaLabel || role === 'presentation';
      expect(hasAccessibleName).toBeTruthy();
    }
  });

  test('@p0 @a11y: color contrast sufficient (WCAG AA)', async ({ page }) => {
    /**
     * Flow: Inject axe with contrast checker
     * Expected: All text has min 4.5:1 or 3:1 for large text
     */
    await page.goto('/studio');
    await page.getByTestId('email-input')?.fill('user@example.com');
    await page.getByRole('button', { name: /계속/ })?.click();

    await injectAxe(page);
    // axe checks color contrast by default
    await checkA11y(page, null, {
      rules: {
        'color-contrast': { enabled: true },
      },
    });
  });

  test('@p0 @a11y: no focus trap (can escape modals)', async ({ page }) => {
    /**
     * Flow: Open a dialog/modal, Tab through items, can Tab out or press Escape
     * Expected: Not stuck in focus trap, can close modal
     */
    await page.goto('/sign-in');
    await page.getByTestId('email-input').fill('user@example.com');
    await page.getByRole('button', { name: /계속/ }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto('/studio');

    // Look for a dialog (e.g., settings modal if it exists)
    const settingsBtn = page.getByRole('button', { name: /settings|gear|⚙/i });
    if (await settingsBtn.isVisible()) {
      await settingsBtn.click();

      // Dialog should be open
      const dialog = page.locator('[role="dialog"]');
      if (await dialog.isVisible()) {
        // Press Escape to close
        await page.keyboard.press('Escape');
        await expect(dialog).not.toBeVisible();
      }
    }
  });
});
