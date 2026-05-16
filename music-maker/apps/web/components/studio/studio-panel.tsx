'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Slider } from '@/components/ui/slider';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { StylePicker } from './style-picker';
import { GenerateButton } from './generate-button';
import { LyricsEditor } from './lyrics-editor';
import { useGenerateSong } from '@/lib/api/hooks/use-generate-song';
import { ApiError } from '@/lib/api/client';
import type {
  GenerateSongRequest,
  GenerationMode,
  LyricsMode,
  MurekaModel,
} from '@/lib/api/types';

const promptSchema = z.object({
  text: z.string().min(3, '최소 3자 이상 입력하세요').max(500),
  length_s: z.number().int().min(15).max(300),
});

interface StudioPanelProps {
  onSubmitted?: (generationId: string) => void;
}

/**
 * StudioPanel — W1 중앙 입력 패널.
 * - 모드 토글 (Song / Instrumental)
 * - 프롬프트 / 길이 / 스타일 / 가사 (탭) / 생성 CTA
 */
export function StudioPanel({ onSubmitted }: StudioPanelProps) {
  const router = useRouter();
  const generateMutation = useGenerateSong();

  const [mode, setMode] = React.useState<GenerationMode>('song');
  const [model] = React.useState<MurekaModel>('mureka-7');
  const [lyricsMode, setLyricsMode] = React.useState<LyricsMode>('none');
  const [lyrics, setLyrics] = React.useState('');
  const [genres, setGenres] = React.useState<string[]>(['Lo-fi']);
  const [instruments, setInstruments] = React.useState<string[]>([]);
  const [moods, setMoods] = React.useState({
    energy: 50,
    brightness: 50,
    complexity: 40,
    bpm: 110,
  });

  const form = useForm({
    resolver: zodResolver(promptSchema),
    defaultValues: { text: '', length_s: 90 },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    const req: GenerateSongRequest = {
      mode,
      prompt: {
        text: values.text,
        length_s: values.length_s,
        genres: genres.map((g) => g.toLowerCase()),
        moods: [],
        bpm: moods.bpm,
        instruments,
      },
      lyrics: lyricsMode === 'user' ? lyrics : null,
      lyrics_mode: lyricsMode,
      model,
    };

    try {
      const result = await generateMutation.mutateAsync(req);
      toast.success('생성 요청 접수됨', {
        description: `예상 ${result.estimated_seconds}초. 진행률 화면으로 이동합니다.`,
      });
      onSubmitted?.(result.generation_id);
      router.push(`/studio/result/${result.generation_id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error('생성 요청 실패', {
          description: err.problem.detail ?? err.problem.title,
        });
      } else {
        toast.error('네트워크 오류', {
          description: '잠시 후 다시 시도해주세요.',
        });
      }
    }
  });

  // Cmd+Enter 단축키 (Desktop)
  React.useEffect(() => {
    const handler = (evt: KeyboardEvent) => {
      if (
        (evt.metaKey || evt.ctrlKey) &&
        evt.key === 'Enter' &&
        !generateMutation.isPending
      ) {
        evt.preventDefault();
        void onSubmit();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onSubmit, generateMutation.isPending]);

  const generateState = generateMutation.isPending
    ? 'loading'
    : generateMutation.isError
      ? 'error'
      : generateMutation.isSuccess
        ? 'success'
        : 'idle';

  return (
    <Card>
      <CardContent className="p-6">
        <form onSubmit={onSubmit} className="space-y-5">
          <div>
            <Label htmlFor="prompt-text">프롬프트</Label>
            <Textarea
              id="prompt-text"
              placeholder="비 오는 도쿄 새벽, 잔잔한 피아노"
              rows={3}
              {...form.register('text')}
              data-testid="prompt-input"
            />
            {form.formState.errors.text && (
              <p className="mt-1 text-body-sm text-danger" role="alert">
                {form.formState.errors.text.message}
              </p>
            )}
          </div>

          <div className="flex items-center gap-4">
            <span className="text-body-sm font-semibold">Mode:</span>
            <label className="flex items-center gap-2 text-body-sm">
              <input
                type="radio"
                name="mode"
                value="song"
                checked={mode === 'song'}
                onChange={() => setMode('song')}
                className="accent-[hsl(var(--accent-primary))]"
              />
              Song
            </label>
            <label className="flex items-center gap-2 text-body-sm">
              <input
                type="radio"
                name="mode"
                value="instrumental"
                checked={mode === 'instrumental'}
                onChange={() => setMode('instrumental')}
                className="accent-[hsl(var(--accent-primary))]"
              />
              Instrumental
            </label>
          </div>

          <div>
            <Label htmlFor="length">
              Length:{' '}
              <span className="font-mono">{form.watch('length_s')}s</span>
            </Label>
            <Slider
              id="length"
              min={15}
              max={300}
              step={15}
              value={[form.watch('length_s')]}
              onValueChange={(v) =>
                form.setValue('length_s', v[0] ?? 90, { shouldValidate: true })
              }
              aria-label="곡 길이"
            />
          </div>

          <Tabs defaultValue="style">
            <TabsList>
              <TabsTrigger value="style">스타일</TabsTrigger>
              <TabsTrigger value="lyrics" disabled={mode === 'instrumental'}>
                가사
              </TabsTrigger>
            </TabsList>
            <TabsContent value="style">
              <StylePicker
                genres={genres}
                moods={moods}
                instruments={instruments}
                onChange={(next) => {
                  if (next.genres !== undefined) setGenres(next.genres);
                  if (next.instruments !== undefined)
                    setInstruments(next.instruments);
                  if (next.moods !== undefined) setMoods(next.moods);
                }}
              />
            </TabsContent>
            <TabsContent value="lyrics">
              <div className="space-y-3">
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setLyricsMode('none')}
                    aria-pressed={lyricsMode === 'none'}
                    className="rounded-md border border-border px-3 py-1 text-body-sm focus-ring data-[active=true]:bg-accent/20"
                    data-active={lyricsMode === 'none'}
                  >
                    가사 없음
                  </button>
                  <button
                    type="button"
                    onClick={() => setLyricsMode('user')}
                    aria-pressed={lyricsMode === 'user'}
                    className="rounded-md border border-border px-3 py-1 text-body-sm focus-ring data-[active=true]:bg-accent/20"
                    data-active={lyricsMode === 'user'}
                  >
                    직접 입력
                  </button>
                  <button
                    type="button"
                    onClick={() => setLyricsMode('ai')}
                    aria-pressed={lyricsMode === 'ai'}
                    className="rounded-md border border-border px-3 py-1 text-body-sm focus-ring data-[active=true]:bg-accent/20"
                    data-active={lyricsMode === 'ai'}
                  >
                    AI 자동 생성
                  </button>
                </div>
                {lyricsMode === 'user' && (
                  <LyricsEditor value={lyrics} onChange={setLyrics} />
                )}
              </div>
            </TabsContent>
          </Tabs>

          <div className="flex flex-col items-center gap-2 pt-2">
            <GenerateButton state={generateState} creditCost={1} />
            <p className="text-body-sm text-muted-foreground">
              <kbd className="rounded border border-border bg-elevated px-1 font-mono text-body-sm">
                ⌘+Enter
              </kbd>{' '}
              로 빠르게 생성
            </p>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
