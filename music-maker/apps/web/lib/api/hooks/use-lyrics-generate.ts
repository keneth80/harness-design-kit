'use client';

import { useMutation } from '@tanstack/react-query';
import { apiFetch } from '../client';
import type {
  LyricsGenerateRequest,
  LyricsGenerateResponse,
} from '../types';

export function useLyricsGenerate() {
  return useMutation({
    mutationFn: (req: LyricsGenerateRequest) =>
      apiFetch<LyricsGenerateResponse>('/lyrics/generate', {
        method: 'POST',
        body: req,
      }),
  });
}
