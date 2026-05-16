'use client';

import { Play, Star } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatDurationMs } from '@/lib/utils/format';
import { usePlayerStore } from '@/lib/store/player-store';
import type { LibraryItem } from '@/lib/api/types';

export function TrackCard({ item }: { item: LibraryItem }) {
  const setTrack = usePlayerStore((s) => s.setTrack);

  return (
    <Card
      className="group cursor-pointer transition-all hover:-translate-y-0.5 hover:shadow-lg"
      data-testid="track-card"
    >
      <CardContent className="space-y-2 p-3">
        <div className="relative aspect-square overflow-hidden rounded-md bg-elevated">
          {item.cover_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={item.cover_url}
              alt={`${item.title} 커버`}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-muted-foreground">
              ♪
            </div>
          )}
          <Button
            size="icon"
            className="absolute inset-0 m-auto h-12 w-12 rounded-full opacity-0 transition-opacity group-hover:opacity-100"
            aria-label={`${item.title} 재생`}
            onClick={() =>
              setTrack({
                id: item.id,
                title: item.title,
                mp3Url: item.mp3_url,
                durationMs: item.duration_ms,
                coverUrl: item.cover_url,
              })
            }
          >
            <Play className="h-5 w-5" aria-hidden />
          </Button>
        </div>
        <div className="flex items-center justify-between">
          <h4 className="truncate text-body-md font-medium">{item.title}</h4>
          {item.is_favorite && (
            <Star
              className="h-3 w-3 shrink-0 text-warning"
              fill="currentColor"
              aria-label="즐겨찾기"
            />
          )}
        </div>
        <p className="font-mono text-body-sm text-muted-foreground">
          {formatDurationMs(item.duration_ms)}
        </p>
        <div className="flex flex-wrap gap-1">
          {item.tags.slice(0, 2).map((tag) => (
            <Badge key={tag} variant="outline" className="text-body-sm">
              #{tag}
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
