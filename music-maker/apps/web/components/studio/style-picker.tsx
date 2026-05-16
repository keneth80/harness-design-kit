'use client';

import * as React from 'react';
import { Slider } from '@/components/ui/slider';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils/cn';

const GENRES = [
  'Lo-fi',
  'K-pop',
  'EDM',
  'Cinematic',
  'Jazz',
  'Rock',
  'Folk',
  'R&B',
  'Hip-hop',
  'Ambient',
  'Chiptune',
  'Trap',
  'Funk',
] as const;

const INSTRUMENTS = [
  'Piano',
  'Guitar',
  'Strings',
  'Synth',
  'Drums',
  'Vocal Pad',
] as const;

interface StylePickerProps {
  genres: string[];
  moods: { energy: number; brightness: number; complexity: number; bpm: number };
  instruments: string[];
  onChange: (
    next: Partial<{
      genres: string[];
      moods: StylePickerProps['moods'];
      instruments: string[];
    }>,
  ) => void;
}

/**
 * StylePicker — W3: 장르 칩 + 분위기 슬라이더 + 악기.
 */
export function StylePicker({
  genres,
  moods,
  instruments,
  onChange,
}: StylePickerProps) {
  const toggleGenre = (g: string) => {
    onChange({
      genres: genres.includes(g)
        ? genres.filter((x) => x !== g)
        : [...genres, g],
    });
  };

  const toggleInstrument = (i: string) => {
    onChange({
      instruments: instruments.includes(i)
        ? instruments.filter((x) => x !== i)
        : [...instruments, i],
    });
  };

  return (
    <div className="space-y-6">
      <section>
        <h4 className="mb-3 text-body-sm font-semibold text-muted-foreground">
          장르 (Genre · 다중 선택)
        </h4>
        <div className="flex flex-wrap gap-2">
          {GENRES.map((g) => (
            <button
              key={g}
              type="button"
              onClick={() => toggleGenre(g)}
              aria-pressed={genres.includes(g)}
              className={cn(
                'rounded-full border px-3 py-1 text-body-sm transition-colors focus-ring',
                genres.includes(g)
                  ? 'border-accent bg-accent/20 text-accent'
                  : 'border-border bg-transparent text-muted-foreground hover:bg-elevated',
              )}
            >
              {g}
              {genres.includes(g) && ' ✓'}
            </button>
          ))}
        </div>
      </section>

      <section>
        <h4 className="mb-3 text-body-sm font-semibold text-muted-foreground">
          분위기 (Mood)
        </h4>
        <div className="space-y-4">
          <MoodSlider
            label="에너지"
            min={0}
            max={100}
            value={moods.energy}
            onChange={(v) => onChange({ moods: { ...moods, energy: v } })}
            leftLabel="낮음"
            rightLabel="높음"
          />
          <MoodSlider
            label="밝기"
            min={0}
            max={100}
            value={moods.brightness}
            onChange={(v) =>
              onChange({ moods: { ...moods, brightness: v } })
            }
            leftLabel="어둡게"
            rightLabel="밝게"
          />
          <MoodSlider
            label="복잡도"
            min={0}
            max={100}
            value={moods.complexity}
            onChange={(v) =>
              onChange({ moods: { ...moods, complexity: v } })
            }
            leftLabel="심플"
            rightLabel="복잡"
          />
          <MoodSlider
            label="속도(BPM)"
            min={60}
            max={180}
            value={moods.bpm}
            onChange={(v) => onChange({ moods: { ...moods, bpm: v } })}
            leftLabel="60"
            rightLabel="180"
          />
        </div>
      </section>

      <section>
        <h4 className="mb-3 text-body-sm font-semibold text-muted-foreground">
          악기 (Optional)
        </h4>
        <div className="flex flex-wrap gap-2">
          {INSTRUMENTS.map((i) => (
            <Badge
              key={i}
              variant={instruments.includes(i) ? 'default' : 'outline'}
              className="cursor-pointer select-none"
              onClick={() => toggleInstrument(i)}
              role="button"
              tabIndex={0}
            >
              {i}
              {instruments.includes(i) && ' ✓'}
            </Badge>
          ))}
        </div>
      </section>
    </div>
  );
}

function MoodSlider({
  label,
  min,
  max,
  value,
  onChange,
  leftLabel,
  rightLabel,
}: {
  label: string;
  min: number;
  max: number;
  value: number;
  onChange: (v: number) => void;
  leftLabel: string;
  rightLabel: string;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-body-sm">
        <span className="text-foreground">{label}</span>
        <span className="font-mono tabular-nums text-muted-foreground">
          {value}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-body-sm text-muted-foreground">{leftLabel}</span>
        <Slider
          min={min}
          max={max}
          step={1}
          value={[value]}
          onValueChange={(v) => onChange(v[0] ?? value)}
          aria-label={label}
          className="flex-1"
        />
        <span className="text-body-sm text-muted-foreground">{rightLabel}</span>
      </div>
    </div>
  );
}
