'use client';

import * as React from 'react';
import { Sparkles } from 'lucide-react';
import { useCredits } from '@/lib/api/hooks/use-credits';
import { Badge } from '@/components/ui/badge';

/**
 * CreditMeter — 우상단 잔여 크레딧 + count-down 애니메이션.
 * 02-UX-Design 5.4: 차감 시 200ms count-down.
 */
export function CreditMeter() {
  const { data, isLoading } = useCredits();
  const [displayed, setDisplayed] = React.useState<number | null>(null);

  // 값이 변하면 count-down 애니메이션
  React.useEffect(() => {
    if (data?.credits === undefined) return;
    if (displayed === null) {
      setDisplayed(data.credits);
      return;
    }
    if (displayed === data.credits) return;
    const start = displayed;
    const end = data.credits;
    const duration = 200;
    const startTime = performance.now();

    let frame: number;
    const step = (now: number) => {
      const t = Math.min(1, (now - startTime) / duration);
      const v = Math.round(start + (end - start) * t);
      setDisplayed(v);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [data?.credits, displayed]);

  if (isLoading || displayed === null) {
    return (
      <Badge variant="outline" aria-label="크레딧 로딩 중">
        <Sparkles className="h-3 w-3" aria-hidden /> ⋯
      </Badge>
    );
  }

  return (
    <Badge
      variant="default"
      aria-label={`잔여 크레딧 ${displayed}`}
      data-testid="credit-meter"
    >
      <Sparkles className="h-3 w-3" aria-hidden /> Credits: {displayed}
    </Badge>
  );
}
