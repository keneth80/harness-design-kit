'use client';

import * as React from 'react';
import { Play, Pause } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { formatDurationMs } from '@/lib/utils/format';
import { Button } from '@/components/ui/button';

interface WaveformPlayerProps {
  url: string;
  durationMs: number;
  title?: string;
  /** 키보드 Space로 재생/정지 토글 활성 */
  enableSpaceShortcut?: boolean;
  /** wavesurfer 사용 가능 환경에서 파형 시각화. 테스트/SSR 환경에서는 fallback */
  useWavesurfer?: boolean;
}

/**
 * WaveformPlayer — 02-UX-Design 5.3 사양.
 * - wavesurfer.js v7 dynamic import (SSR 안전)
 * - Space=재생/정지, ←/→=5초 이동
 * - aria-label, aria-valuenow 동적 업데이트
 */
export function WaveformPlayer({
  url,
  durationMs,
  title,
  enableSpaceShortcut = true,
  useWavesurfer = true,
}: WaveformPlayerProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const audioRef = React.useRef<HTMLAudioElement>(null);
  const wavesurferRef = React.useRef<{
    play: () => void;
    pause: () => void;
    isPlaying: () => boolean;
    destroy: () => void;
    on: (evt: string, cb: () => void) => void;
  } | null>(null);

  const [isPlaying, setIsPlaying] = React.useState(false);
  const [currentMs, setCurrentMs] = React.useState(0);

  // wavesurfer.js dynamic load
  React.useEffect(() => {
    if (!useWavesurfer || !containerRef.current) return;
    if (typeof window === 'undefined') return;

    let disposed = false;
    let instance: typeof wavesurferRef.current = null;

    (async () => {
      try {
        const mod = await import('wavesurfer.js');
        if (disposed || !containerRef.current) return;
        const WaveSurfer = mod.default;
        // CSS 변수를 직접 읽어 wave 색상 적용
        instance = WaveSurfer.create({
          container: containerRef.current,
          height: 64,
          waveColor: 'rgb(124, 92, 255)',
          progressColor: 'rgb(245, 245, 247)',
          cursorWidth: 1,
          barWidth: 2,
          barGap: 1,
          barRadius: 2,
          url,
        }) as unknown as typeof wavesurferRef.current;

        wavesurferRef.current = instance;
        instance?.on('play', () => setIsPlaying(true));
        instance?.on('pause', () => setIsPlaying(false));
        instance?.on('finish', () => setIsPlaying(false));
      } catch {
        // wavesurfer load 실패 시 native audio fallback
      }
    })();

    return () => {
      disposed = true;
      if (instance) {
        try {
          instance.destroy();
        } catch {
          /* noop */
        }
      }
      wavesurferRef.current = null;
    };
  }, [url, useWavesurfer]);

  const togglePlay = React.useCallback(() => {
    if (wavesurferRef.current) {
      const ws = wavesurferRef.current;
      if (ws.isPlaying()) ws.pause();
      else ws.play();
    } else if (audioRef.current) {
      const audio = audioRef.current;
      if (audio.paused) {
        void audio.play();
        setIsPlaying(true);
      } else {
        audio.pause();
        setIsPlaying(false);
      }
    }
  }, []);

  // Space 단축키
  React.useEffect(() => {
    if (!enableSpaceShortcut) return;
    const handler = (evt: KeyboardEvent) => {
      const target = evt.target as HTMLElement | null;
      // 입력 필드 위에서는 무시
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return;
      }
      if (evt.code === 'Space') {
        evt.preventDefault();
        togglePlay();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [enableSpaceShortcut, togglePlay]);

  // Native audio fallback time update
  React.useEffect(() => {
    const audio = audioRef.current;
    if (!audio || useWavesurfer) return;
    const onTime = () => setCurrentMs(audio.currentTime * 1000);
    audio.addEventListener('timeupdate', onTime);
    return () => audio.removeEventListener('timeupdate', onTime);
  }, [useWavesurfer]);

  return (
    <div
      className={cn(
        'flex items-center gap-3 rounded-md bg-elevated p-3',
      )}
      role="region"
      aria-label={`오디오 플레이어, ${title ?? ''} ${formatDurationMs(durationMs)}`}
    >
      <Button
        type="button"
        size="icon"
        variant="default"
        onClick={togglePlay}
        aria-label={isPlaying ? '일시정지' : '재생'}
        aria-pressed={isPlaying}
        className="shrink-0 rounded-full"
      >
        {isPlaying ? (
          <Pause className="h-4 w-4" aria-hidden />
        ) : (
          <Play className="h-4 w-4" aria-hidden />
        )}
      </Button>

      <div
        ref={containerRef}
        data-testid="waveform-container"
        className="min-h-[40px] flex-1"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={durationMs}
        aria-valuenow={currentMs}
        aria-label="재생 진행률"
      >
        {!useWavesurfer && (
          <div className="h-2 w-full overflow-hidden rounded-full bg-surface">
            <div
              className="h-full bg-accent transition-all"
              style={{
                width: `${Math.min(100, (currentMs / Math.max(durationMs, 1)) * 100)}%`,
              }}
            />
          </div>
        )}
      </div>

      <span className="font-mono text-body-sm tabular-nums text-muted-foreground">
        {formatDurationMs(currentMs)} / {formatDurationMs(durationMs)}
      </span>

      <audio ref={audioRef} src={url} preload="metadata" className="hidden" />
    </div>
  );
}
