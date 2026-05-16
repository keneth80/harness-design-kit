import { API_BASE } from './client';
import type { GenerationEvent } from './types';

/**
 * SSE 구독.
 * 실패 시 polling fallback은 hook 측에서 처리.
 */
export function subscribeGenerationEvents(
  generationId: string,
  onEvent: (evt: GenerationEvent) => void,
  onError?: (err: Event) => void,
): () => void {
  const url = `${API_BASE}/events/${generationId}`;
  const source = new EventSource(url, { withCredentials: true });

  source.onmessage = (msg: MessageEvent<string>) => {
    try {
      const parsed = JSON.parse(msg.data) as GenerationEvent;
      onEvent(parsed);
    } catch (err) {
      // malformed event — 무시 (서버측 로깅 책임)
      // eslint-disable-next-line no-console
      console.warn('SSE parse error', err);
    }
  };

  source.onerror = (err) => {
    if (onError) onError(err);
    // EventSource는 자동 재연결 — 명시적 close는 client가 cleanup 시
  };

  return () => source.close();
}
