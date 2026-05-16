import { describe, it, expect } from 'vitest';
import { formatDurationMs } from '@/lib/utils/format';

describe('formatDurationMs', () => {
  it('formats 0 as 0:00', () => {
    expect(formatDurationMs(0)).toBe('0:00');
  });
  it('formats 90s as 1:30', () => {
    expect(formatDurationMs(90_000)).toBe('1:30');
  });
  it('pads single-digit seconds', () => {
    expect(formatDurationMs(65_000)).toBe('1:05');
  });
  it('returns 0:00 for invalid inputs', () => {
    expect(formatDurationMs(-1)).toBe('0:00');
    expect(formatDurationMs(NaN)).toBe('0:00');
  });
});
