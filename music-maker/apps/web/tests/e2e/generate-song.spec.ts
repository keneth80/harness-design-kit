import { test, expect } from '@playwright/test';

/**
 * E2E #1 — 첫 곡 생성 시나리오 (MSW로 BE 모킹).
 * Flow:
 *  1) 로그인 (mock)
 *  2) Studio 진입
 *  3) 프롬프트 입력
 *  4) Generate 클릭
 *  5) 진행률 노출
 *  6) A/B 결과 노출 + 다운로드 버튼 확인
 */
test('generate song happy path', async ({ page }) => {
  // 1) 로그인
  await page.goto('/sign-in');
  await page.getByTestId('email-input').fill('user@example.com');
  await page.getByRole('button', { name: /계속/ }).click();

  // 2) Dashboard → Studio
  await expect(page).toHaveURL(/\/dashboard/);
  await page.goto('/studio');

  // 3) 프롬프트 입력
  const prompt = page.getByTestId('prompt-input');
  await expect(prompt).toBeVisible();
  await prompt.fill('비 오는 도쿄 새벽, 잔잔한 피아노');

  // 4) Generate 클릭
  await page.getByRole('button', { name: /Generate/i }).click();

  // 5) result 페이지로 이동 + 진행률 노출
  await expect(page).toHaveURL(/\/studio\/result\//, { timeout: 10_000 });
  await expect(page.getByText(/생성 중/)).toBeVisible();

  // 6) A/B 결과 (MSW가 ~2초 내 완료 이벤트 푸시)
  await expect(page.getByTestId('track-A')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId('track-B')).toBeVisible();
  await expect(page.getByTestId('download-A-mp3')).toBeVisible();
  await expect(page.getByTestId('download-B-wav')).toBeVisible();
});
