'use client';

import * as React from 'react';
import { Sparkles, Check, Clock, Pause } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';

// W4 사양: 진행 단계
const STAGES = [
  { key: 'lyrics_parsed', label: '가사 분석' },
  { key: 'melody', label: '멜로디 구성' },
  { key: 'vocal_synthesis', label: '보컬 합성' },
  { key: 'mastering', label: '마스터링' },
  { key: 'completed', label: '완료' },
] as const;

const TIPS = [
  '다운로드한 음원은 YouTube Content ID에 등록되지 않으니 안심하고 사용하세요.',
  '같은 프롬프트로 2개의 변주(A/B)가 자동 생성됩니다.',
  '스템 분리는 결과 화면의 "⋯" 메뉴에서 요청할 수 있어요.',
  '평균 생성 시간은 45초, 길이가 길수록 조금 더 걸려요.',
  '한국어 가사 보컬 합성은 Mureka가 잘 다루는 영역입니다.',
  '실패 시 크레딧은 자동으로 환불됩니다.',
  '프리셋을 저장하면 다음 번에 같은 톤을 재현할 수 있어요.',
  '백그라운드로 보내도 완료 시 토스트로 알려드려요.',
] as const;

interface GenerationProgressProps {
  progress: number; // 0-100
  stage: string;
  estimatedRemainingS: number;
  onSendBackground?: () => void;
}

export function GenerationProgress({
  progress,
  stage,
  estimatedRemainingS,
  onSendBackground,
}: GenerationProgressProps) {
  const [tipIndex, setTipIndex] = React.useState(0);

  // 팁 6초마다 회전
  React.useEffect(() => {
    const id = setInterval(() => {
      setTipIndex((i) => (i + 1) % TIPS.length);
    }, 6000);
    return () => clearInterval(id);
  }, []);

  const currentStageIdx = React.useMemo(() => {
    const idx = STAGES.findIndex((s) => s.key === stage);
    return idx >= 0 ? idx : 0;
  }, [stage]);

  return (
    <Card className="mx-auto max-w-2xl">
      <CardContent className="space-y-6 p-8 text-center">
        <h2 className="flex items-center justify-center gap-2 text-heading-lg">
          <Sparkles className="h-6 w-6 text-accent" aria-hidden />
          음원 생성 중
          <Sparkles className="h-6 w-6 text-accent" aria-hidden />
        </h2>

        <div className="space-y-2">
          <Progress
            value={progress}
            aria-label="생성 진행률"
            aria-valuenow={progress}
          />
          <p className="font-mono text-body-sm tabular-nums text-muted-foreground">
            {progress}% · 약 {Math.max(0, Math.round(estimatedRemainingS))}초
            남음
          </p>
        </div>

        <div className="rounded-md border border-border bg-elevated p-4 text-left">
          <p className="mb-3 text-body-sm font-semibold text-muted-foreground">
            진행 단계
          </p>
          <ul className="space-y-2">
            {STAGES.map((s, i) => {
              const done = i < currentStageIdx;
              const active = i === currentStageIdx;
              return (
                <li
                  key={s.key}
                  className={cn(
                    'flex items-center gap-3 text-body-md',
                    done && 'text-success',
                    active && 'text-accent',
                    !done && !active && 'text-muted-foreground',
                  )}
                >
                  <span aria-hidden>
                    {done ? (
                      <Check className="h-4 w-4" />
                    ) : active ? (
                      <Clock className="h-4 w-4 animate-pulse" />
                    ) : (
                      <Pause className="h-4 w-4" />
                    )}
                  </span>
                  <span>{s.label}</span>
                  {active && (
                    <span className="ml-auto font-mono text-body-sm">
                      진행 중…
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>

        <p
          key={tipIndex}
          className="animate-fade-in text-body-sm text-muted-foreground"
          aria-live="polite"
        >
          💡 팁: {TIPS[tipIndex]}
        </p>

        {onSendBackground && (
          <button
            type="button"
            onClick={onSendBackground}
            className="text-body-sm text-accent underline-offset-4 hover:underline focus-ring"
          >
            ← 백그라운드로 보내기
          </button>
        )}
      </CardContent>
    </Card>
  );
}
