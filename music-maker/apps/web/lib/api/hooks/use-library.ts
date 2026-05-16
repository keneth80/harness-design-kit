'use client';

import { useInfiniteQuery } from '@tanstack/react-query';
import { apiFetch } from '../client';
import type { LibraryResponse } from '../types';

interface LibraryFilter {
  genres?: string[];
  favorites?: boolean;
  project_id?: string;
}

export function useLibrary(filter: LibraryFilter = {}) {
  return useInfiniteQuery({
    queryKey: ['library', filter],
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams();
      if (pageParam) params.set('cursor', pageParam);
      params.set('limit', '24');
      if (filter.genres?.length)
        params.set('filter[genres]', filter.genres.join(','));
      if (filter.favorites) params.set('filter[favorites]', 'true');
      if (filter.project_id)
        params.set('filter[project_id]', filter.project_id);
      return apiFetch<LibraryResponse>(`/library?${params.toString()}`);
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
}
