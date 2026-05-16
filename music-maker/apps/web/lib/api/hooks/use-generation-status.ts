'use client';

import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiFetch, API_BASE } from '../client';
import { useGenerationStore } from '@/lib/store/generation-store';
import type {
  GenerationEvent,
  GenerationStatusResponse,
} from '../types';

const POLL_FALLBACK_INTERVAL_MS = 5000;

/**
 * SSE로 생성 진행률 구독, 실패 시 5초 폴링 fallback.
 * 02-UX-Design Flow #1 + 03-Architecture 5.3 SSE Event Schema.
 */
export function useGenerationStatus(generationId: string | null) {
  const queryClient = useQueryClient();
  const upsert = useGenerationStore((s) => s.upsert);
  const [connected, setConnected] = useState(false);
  const fallbackTimer = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!generationId) return;

    let cleanupCalled = false;
    let source: EventSource | null = null;

    const startPolling = () => {
      if (fallbackTimer.current) return;
      fallbackTimer.current = setInterval(async () => {
        try {
          const res = await apiFetch<GenerationStatusResponse>(
            `/songs/${generationId}`,
          );
          handleStatusResponse(res);
        } catch {
          // 폴링 실패는 silent — 다음 tick에 재시도
        }
      }, POLL_FALLBACK_INTERVAL_MS);
    };

    const stopPolling = () => {
      if (fallbackTimer.current) {
        clearInterval(fallbackTimer.current);
        fallbackTimer.current = null;
      }
    };

    const handleStatusResponse = (res: GenerationStatusResponse) => {
      if (res.status === 'completed') {
        upsert({
          id: res.generation_id,
          status: 'completed',
          progress: 100,
          stage: 'completed',
          estimatedRemainingS: 0,
          startedAt: new Date().toISOString(),
          songs: res.songs,
        });
        toast.success('음원 생성 완료!', {
          description: '2개 트랙이 준비되었습니다.',
        });
        queryClient.invalidateQueries({ queryKey: ['library'] });
        stopPolling();
      } else if (res.status === 'failed' || res.status === 'cancelled') {
        upsert({
          id: res.generation_id,
          status: res.status,
          progress: 0,
          stage: 'failed',
          estimatedRemainingS: 0,
          startedAt: new Date().toISOString(),
          error: { code: res.error_code, message: res.error_message },
        });
        toast.error('생성 실패', {
          description: `크레딧이 환불되었습니다 (+${res.refunded})`,
        });
        queryClient.invalidateQueries({ queryKey: ['credits'] });
        stopPolling();
      } else if (res.status === 'processing' || res.status === 'queued') {
        upsert({
          id: res.generation_id,
          status: res.status,
          progress: res.progress,
          stage: res.stage,
          estimatedRemainingS: res.estimated_remaining_s,
          startedAt: res.started_at,
        });
      }
    };

    const handleEvent = (evt: GenerationEvent) => {
      switch (evt.event) {
        case 'progress':
          upsert({
            id: generationId,
            status: 'processing',
            progress: evt.progress,
            stage: evt.stage,
            estimatedRemainingS: evt.estimated_remaining_s ?? 0,
            startedAt: new Date().toISOString(),
          });
          break;
        case 'completed':
          upsert({
            id: generationId,
            status: 'completed',
            progress: 100,
            stage: 'completed',
            estimatedRemainingS: 0,
            startedAt: new Date().toISOString(),
            songs: evt.songs,
          });
          toast.success('음원 생성 완료!');
          queryClient.invalidateQueries({ queryKey: ['library'] });
          break;
        case 'failed':
          upsert({
            id: generationId,
            status: 'failed',
            progress: 0,
            stage: 'failed',
            estimatedRemainingS: 0,
            startedAt: new Date().toISOString(),
            error: { code: evt.error, message: evt.error },
          });
          toast.error('생성 실패', {
            description: `크레딧이 환불되었습니다 (+${evt.refunded})`,
          });
          queryClient.invalidateQueries({ queryKey: ['credits'] });
          break;
        case 'retrying':
          toast.info(`재시도 중 (${evt.attempt})`);
          break;
        case 'ping':
        case 'queued':
        default:
          break;
      }
    };

    try {
      source = new EventSource(`${API_BASE}/events/${generationId}`);
      source.onopen = () => {
        if (!cleanupCalled) setConnected(true);
      };
      source.onmessage = (msg: MessageEvent<string>) => {
        try {
          const parsed = JSON.parse(msg.data) as GenerationEvent;
          handleEvent(parsed);
        } catch {
          /* malformed event */
        }
      };
      source.onerror = () => {
        // SSE 실패 시 폴링 fallback 시작
        if (!cleanupCalled) {
          setConnected(false);
          startPolling();
        }
      };
    } catch {
      // EventSource 미지원 환경
      startPolling();
    }

    return () => {
      cleanupCalled = true;
      if (source) source.close();
      stopPolling();
    };
  }, [generationId, queryClient, upsert]);

  return { connected };
}
