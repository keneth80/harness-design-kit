'use client';

import * as React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider as NextThemes } from 'next-themes';
import { Toaster } from 'sonner';

/**
 * App-wide providers:
 * - ThemeProvider (dark default per 02-UX-Design P2)
 * - QueryClient (TanStack Query)
 * - Sonner Toaster (top-right)
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );

  // MSW dev 모드 시작 (브라우저 환경)
  React.useEffect(() => {
    if (typeof window === 'undefined') return;
    if (process.env.NEXT_PUBLIC_USE_MSW !== 'true') return;

    void (async () => {
      try {
        const { startMockWorker } = await import('@/tests/mocks/browser');
        await startMockWorker();
      } catch (err) {
        // dev 환경에서만 동작; 무시
        // eslint-disable-next-line no-console
        console.warn('[MSW] start failed', err);
      }
    })();
  }, []);

  return (
    <NextThemes attribute="class" defaultTheme="dark" enableSystem={false}>
      <QueryClientProvider client={queryClient}>
        {children}
        <Toaster
          position="top-right"
          theme="dark"
          richColors
          closeButton
        />
      </QueryClientProvider>
    </NextThemes>
  );
}
