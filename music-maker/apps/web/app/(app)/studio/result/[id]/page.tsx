'use client';

import * as React from 'react';
import { useParams } from 'next/navigation';
import { GenerationProgress } from '@/components/studio/generation-progress';
import { AbCompare } from '@/components/studio/ab-compare';
import { useGenerationStatus } from '@/lib/api/hooks/use-generation-status';
import { useGenerationStore } from '@/lib/store/generation-store';
import { toast } from 'sonner';
import type { SongPublic } from '@/lib/api/types';

export default function ResultPage() {
  const params = useParams<{ id: string }>();
  const generationId = params?.id ?? null;

  useGenerationStatus(generationId);
  const active = useGenerationStore((s) =>
    generationId ? s.active[generationId] : undefined,
  );

  const handleDownload = (song: SongPublic, format: 'mp3' | 'wav') => {
    const url = format === 'mp3' ? song.mp3_url : song.wav_url;
    toast.success('다운로드 시작…', { description: `${format.toUpperCase()}` });
    const a = document.createElement('a');
    a.href = url;
    a.download = `track-${song.variant}.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  if (!generationId) return null;

  if (!active || active.status === 'queued' || active.status === 'processing') {
    return (
      <div className="container mx-auto p-6">
        <GenerationProgress
          progress={active?.progress ?? 5}
          stage={active?.stage ?? 'submitted'}
          estimatedRemainingS={active?.estimatedRemainingS ?? 45}
        />
      </div>
    );
  }

  if (active.status === 'failed' || active.status === 'cancelled') {
    return (
      <div className="container mx-auto p-6">
        <div
          role="alert"
          className="rounded-md border border-danger/40 bg-danger/10 p-6 text-body-md text-danger"
        >
          <h2 className="mb-2 text-heading-md">생성 실패</h2>
          <p>{active.error?.message ?? '알 수 없는 오류'}</p>
          <p className="mt-2 text-body-sm text-muted-foreground">
            크레딧이 환불되었습니다. 다시 시도해주세요.
          </p>
        </div>
      </div>
    );
  }

  if (active.status === 'completed' && active.songs) {
    return (
      <div className="container mx-auto p-6">
        <AbCompare
          songs={active.songs}
          onDownload={handleDownload}
          onFavorite={() => toast.success('즐겨찾기에 추가됨')}
        />
      </div>
    );
  }

  return null;
}
