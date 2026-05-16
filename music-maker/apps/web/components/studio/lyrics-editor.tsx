'use client';

import * as React from 'react';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';

const STRUCTURE_TAGS = [
  'Verse',
  'Chorus',
  'Bridge',
  'Outro',
  'Hook',
] as const;

interface LyricsEditorProps {
  value: string;
  onChange: (value: string) => void;
  moderationPassed?: boolean;
}

/**
 * LyricsEditor — 02-UX-Design W2.
 * - 구조 태그 [Verse]/[Chorus]/[Bridge] 자동 삽입
 * - 실시간 라인 수 + 음절 수 카운트
 */
export function LyricsEditor({
  value,
  onChange,
  moderationPassed = true,
}: LyricsEditorProps) {
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  const insertTag = React.useCallback(
    (tag: string) => {
      const insertion = `\n[${tag}]\n`;
      const ta = textareaRef.current;
      if (!ta) {
        onChange(value + insertion);
        return;
      }
      const start = ta.selectionStart ?? value.length;
      const end = ta.selectionEnd ?? value.length;
      const next = value.slice(0, start) + insertion + value.slice(end);
      onChange(next);
      // 커서 이동
      requestAnimationFrame(() => {
        ta.focus();
        ta.selectionStart = ta.selectionEnd = start + insertion.length;
      });
    },
    [value, onChange],
  );

  const stats = React.useMemo(() => {
    const lines = value
      .split('\n')
      .filter((l) => l.trim() && !l.trim().startsWith('['));
    const syllables = value.replace(/\s+/g, '').length; // 간이 추정 (한글=1음절)
    const estimatedSeconds = Math.round((lines.length * 6) / 1.0); // 라인당 약 6초
    return {
      lineCount: lines.length,
      syllableCount: syllables,
      estimatedSeconds,
    };
  }, [value]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-body-sm text-muted-foreground">구조 추가:</span>
        {STRUCTURE_TAGS.map((tag) => (
          <Button
            key={tag}
            type="button"
            variant="outline"
            size="sm"
            onClick={() => insertTag(tag)}
            data-testid={`insert-${tag.toLowerCase()}`}
          >
            <Plus className="h-3 w-3" aria-hidden /> {tag}
          </Button>
        ))}
      </div>

      <Textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="가사를 입력하거나 위 버튼으로 구조 태그를 삽입하세요&#10;[Verse 1]&#10;도시는 잠들지 않아"
        rows={10}
        className={cn(
          'font-mono text-body-md',
          !moderationPassed && 'border-danger',
        )}
        aria-label="가사 에디터"
        data-testid="lyrics-textarea"
      />

      <div className="flex items-center justify-between text-body-sm text-muted-foreground">
        <span data-testid="lyrics-stats">
          <span data-testid="line-count">{stats.lineCount}</span> lines ·{' '}
          <span data-testid="syllable-count">{stats.syllableCount}</span>{' '}
          syllables · 예상{' '}
          <span data-testid="estimated-seconds">{stats.estimatedSeconds}</span>초
        </span>
        {moderationPassed ? (
          <Badge variant="success">⚠ 모더레이션 PASS</Badge>
        ) : (
          <Badge variant="danger">모더레이션 검토 필요</Badge>
        )}
      </div>
    </div>
  );
}
