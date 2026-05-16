import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GenerationProgress } from '@/components/studio/generation-progress';

describe('GenerationProgress', () => {
  it('shows current progress and remaining seconds', () => {
    render(
      <GenerationProgress
        progress={42}
        stage="vocal_synthesis"
        estimatedRemainingS={26}
      />,
    );
    expect(screen.getByText(/42% · 약 26초 남음/)).toBeInTheDocument();
  });

  it('marks earlier stages as completed', () => {
    render(
      <GenerationProgress
        progress={80}
        stage="mastering"
        estimatedRemainingS={5}
      />,
    );
    // mastering 단계 = index 3 → 이전 단계들(가사 분석, 멜로디, 보컬)이 모두 완료
    expect(screen.getByText('가사 분석')).toBeInTheDocument();
    expect(screen.getByText('멜로디 구성')).toBeInTheDocument();
    expect(screen.getByText('보컬 합성')).toBeInTheDocument();
    expect(screen.getByText('마스터링')).toBeInTheDocument();
  });

  it('uses aria-live for tips region', () => {
    render(
      <GenerationProgress
        progress={10}
        stage="lyrics_parsed"
        estimatedRemainingS={40}
      />,
    );
    // 팁 영역에 aria-live='polite' 있어야 함
    const tip = screen.getByText(/팁:/);
    expect(tip).toHaveAttribute('aria-live', 'polite');
  });
});
