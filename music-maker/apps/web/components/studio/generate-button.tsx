'use client';

import * as React from 'react';
import { Sparkles, Loader2, Check, X } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { Button, type ButtonProps } from '@/components/ui/button';

type GenerateState = 'idle' | 'loading' | 'success' | 'error';

interface GenerateButtonProps extends Omit<ButtonProps, 'children'> {
  state?: GenerateState;
  creditCost?: number;
  label?: string;
}

/**
 * GenerateButton — 02-UX-Design 5.1 파동 ripple 애니메이션.
 * 상태: idle → hover → press → loading → success/error → idle
 */
export function GenerateButton({
  state = 'idle',
  creditCost = 1,
  label = 'Generate',
  className,
  disabled,
  ...props
}: GenerateButtonProps) {
  const isLoading = state === 'loading';

  return (
    <div className="flex flex-col items-center gap-2">
      <Button
        size="lg"
        type="submit"
        disabled={disabled || isLoading}
        aria-busy={isLoading}
        className={cn(
          'btn-ripple relative min-w-[200px] rounded-lg text-body-lg font-semibold',
          isLoading && 'is-loading',
          state === 'error' && 'animate-shake bg-danger',
          state === 'success' && 'bg-success',
          className,
        )}
        {...props}
      >
        {state === 'idle' && (
          <>
            <Sparkles className="h-5 w-5" aria-hidden />
            <span>{label}</span>
          </>
        )}
        {state === 'loading' && (
          <>
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
            <span>생성 중…</span>
          </>
        )}
        {state === 'success' && (
          <>
            <Check className="h-5 w-5" aria-hidden />
            <span>완료</span>
          </>
        )}
        {state === 'error' && (
          <>
            <X className="h-5 w-5" aria-hidden />
            <span>실패</span>
          </>
        )}
      </Button>
      <span className="text-body-sm text-muted-foreground">
        cost: {creditCost} credit{creditCost !== 1 ? 's' : ''}
      </span>
    </div>
  );
}
