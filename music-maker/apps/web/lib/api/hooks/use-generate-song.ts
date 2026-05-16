'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../client';
import type {
  GenerateSongRequest,
  GenerateSongResponse,
  CreditsResponse,
} from '../types';

/**
 * POST /api/v1/songs — 음원 생성 요청 (비동기, 즉시 generation_id 반환).
 * 성공 시 optimistic credit decrement.
 */
export function useGenerateSong() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (req: GenerateSongRequest) =>
      apiFetch<GenerateSongResponse>('/songs', {
        method: 'POST',
        body: req,
      }),
    onSuccess: (data) => {
      // optimistic credit update
      queryClient.setQueryData<CreditsResponse | undefined>(
        ['credits'],
        (prev) =>
          prev
            ? { ...prev, credits: data.credits_remaining }
            : prev,
      );
    },
  });
}
