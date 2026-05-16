'use client';

import { Download, Heart, Star, MoreHorizontal, RefreshCcw } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { WaveformPlayer } from './waveform-player';
import type { SongPublic } from '@/lib/api/types';

interface AbCompareProps {
  songs: SongPublic[];
  lyrics?: string;
  licensePdfUrl?: string;
  onRegenerate?: () => void;
  onDownload?: (song: SongPublic, format: 'mp3' | 'wav') => void;
  onFavorite?: (song: SongPublic) => void;
}

/**
 * AbCompare — W5: A/B 결과 비교.
 * 두 트랙 좌우 배치, 각각 파형 플레이어 + 메타 + 다운로드.
 */
export function AbCompare({
  songs,
  lyrics,
  licensePdfUrl,
  onRegenerate,
  onDownload,
  onFavorite,
}: AbCompareProps) {
  const trackA = songs.find((s) => s.variant === 'A') ?? songs[0];
  const trackB = songs.find((s) => s.variant === 'B') ?? songs[1];

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <p className="text-body-md">
          ✨ 생성 완료 · {songs.length}개 트랙 · 1 크레딧 사용
        </p>
        {onRegenerate && (
          <Button variant="outline" size="sm" onClick={onRegenerate}>
            <RefreshCcw className="h-4 w-4" aria-hidden /> 같은 설정으로 재생성
          </Button>
        )}
      </header>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {[trackA, trackB].filter(Boolean).map((song) => (
          <Card key={song.id} data-testid={`track-${song.variant}`}>
            <CardContent className="space-y-4 p-4">
              <WaveformPlayer
                url={song.mp3_url}
                durationMs={song.duration_ms}
                title={`Track ${song.variant}`}
                enableSpaceShortcut={false}
              />
              <div>
                <h3 className="text-heading-md">Track {song.variant}</h3>
                <p className="font-mono text-body-sm text-muted-foreground">
                  BPM {song.bpm} · Key {song.key} ·{' '}
                  {Math.floor(song.duration_ms / 1000)}s
                </p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {song.genres.map((g) => (
                    <Badge key={g} variant="outline">
                      {g}
                    </Badge>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onFavorite?.(song)}
                  aria-label="좋아요"
                >
                  <Heart className="h-4 w-4" aria-hidden /> 좋아요
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onFavorite?.(song)}
                  aria-label="즐겨찾기"
                >
                  <Star className="h-4 w-4" aria-hidden /> 즐겨찾기
                </Button>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  variant="default"
                  size="sm"
                  onClick={() => onDownload?.(song, 'mp3')}
                  data-testid={`download-${song.variant}-mp3`}
                >
                  <Download className="h-4 w-4" aria-hidden /> MP3 320
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onDownload?.(song, 'wav')}
                  data-testid={`download-${song.variant}-wav`}
                >
                  <Download className="h-4 w-4" aria-hidden /> WAV 16bit
                </Button>
                <Button variant="ghost" size="sm" aria-label="추가 메뉴">
                  <MoreHorizontal className="h-4 w-4" aria-hidden />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {lyrics && (
        <Card>
          <CardContent className="p-4">
            <h4 className="mb-2 text-body-sm font-semibold text-muted-foreground">
              가사 (Track A/B 공통)
            </h4>
            <pre className="whitespace-pre-wrap font-mono text-body-sm text-foreground">
              {lyrics}
            </pre>
          </CardContent>
        </Card>
      )}

      {licensePdfUrl && (
        <p className="text-body-sm text-muted-foreground">
          ⓘ 사용 권리 증명서:{' '}
          <a
            href={licensePdfUrl}
            target="_blank"
            rel="noreferrer"
            className="text-accent underline-offset-4 hover:underline"
          >
            PDF 다운로드
          </a>
        </p>
      )}
    </div>
  );
}
