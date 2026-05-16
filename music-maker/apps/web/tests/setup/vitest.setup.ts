import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import { server } from '../mocks/node';

// MSW lifecycle
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());

// jsdom 환경에서 EventSource 미지원 → 더미 클래스
class MockEventSource {
  url: string;
  onmessage: ((evt: MessageEvent<string>) => void) | null = null;
  onerror: ((evt: Event) => void) | null = null;
  onopen: (() => void) | null = null;
  readyState = 0;
  constructor(url: string) {
    this.url = url;
  }
  close() {
    this.readyState = 2;
  }
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() {
    return true;
  }
}
if (!globalThis.EventSource) {
  // @ts-expect-error — jsdom shim
  globalThis.EventSource = MockEventSource;
}

// wavesurfer.js 모킹
vi.mock('wavesurfer.js', () => {
  return {
    default: {
      create: () => {
        const listeners: Record<string, Array<() => void>> = {};
        return {
          play: vi.fn(),
          pause: vi.fn(),
          isPlaying: () => false,
          destroy: vi.fn(),
          on: (evt: string, cb: () => void) => {
            listeners[evt] = listeners[evt] ?? [];
            listeners[evt].push(cb);
          },
        };
      },
    },
  };
});

// next/navigation 부분 모킹 (useRouter / useParams)
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useParams: () => ({ id: '01HXG7E2K4Q' }),
  usePathname: () => '/studio',
}));
