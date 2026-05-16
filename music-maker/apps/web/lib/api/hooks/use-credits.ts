'use client';

import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../client';
import type { CreditsResponse } from '../types';

export function useCredits() {
  return useQuery({
    queryKey: ['credits'],
    queryFn: () => apiFetch<CreditsResponse>('/account/credits'),
    staleTime: 30_000,
  });
}
