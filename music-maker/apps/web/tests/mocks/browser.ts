import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

/**
 * 브라우저 환경에서 MSW worker 시작.
 * NEXT_PUBLIC_USE_MSW=true 일 때 providers.tsx에서 호출.
 */
export const worker = setupWorker(...handlers);

export async function startMockWorker() {
  await worker.start({
    onUnhandledRequest: 'bypass',
    serviceWorker: { url: '/mockServiceWorker.js' },
  });
}
