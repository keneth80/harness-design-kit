'use client';

import { useLibrary } from '@/lib/api/hooks/use-library';
import { TrackCard } from './track-card';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';

export function LibraryGrid() {
  const query = useLibrary();

  if (query.isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="aspect-square w-full" />
        ))}
      </div>
    );
  }

  if (query.isError) {
    return (
      <div className="rounded-md border border-danger/40 bg-danger/10 p-4 text-body-md text-danger">
        라이브러리를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.
      </div>
    );
  }

  const items = query.data?.pages.flatMap((p) => p.items) ?? [];

  if (items.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border p-10 text-center text-muted-foreground">
        아직 생성된 트랙이 없습니다. Studio에서 첫 곡을 만들어보세요.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {items.map((item) => (
          <TrackCard key={item.id} item={item} />
        ))}
      </div>
      {query.hasNextPage && (
        <div className="flex justify-center">
          <Button
            variant="outline"
            onClick={() => query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
          >
            {query.isFetchingNextPage ? '불러오는 중…' : '더 보기'}
          </Button>
        </div>
      )}
    </div>
  );
}
