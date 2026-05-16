import { http, HttpResponse, delay } from 'msw';
import type {
  GenerateSongResponse,
  GenerationStatusResponse,
  LibraryResponse,
  CreditsResponse,
  LyricsGenerateResponse,
  SongPublic,
} from '@/lib/api/types';

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000/api/v1';

const SAMPLE_GENERATION_ID = '01HXG7E2K4Q';
const SAMPLE_SONGS: SongPublic[] = [
  {
    id: '01HXG8A',
    variant: 'A',
    mp3_url:
      'https://cdn.music-maker.app/s/A.mp3?sig=mock',
    wav_url:
      'https://cdn.music-maker.app/s/A.wav?sig=mock',
    duration_ms: 90000,
    bpm: 90,
    key: 'Cm',
    genres: ['lo-fi'],
    moods: ['melancholy'],
    cover_url: 'https://cdn.music-maker.app/c/A.jpg',
  },
  {
    id: '01HXG8B',
    variant: 'B',
    mp3_url:
      'https://cdn.music-maker.app/s/B.mp3?sig=mock',
    wav_url:
      'https://cdn.music-maker.app/s/B.wav?sig=mock',
    duration_ms: 90000,
    bpm: 92,
    key: 'Am',
    genres: ['lo-fi'],
    moods: ['melancholy'],
    cover_url: 'https://cdn.music-maker.app/c/B.jpg',
  },
];

// 폴링 카운터: 호출 횟수에 따라 progress 진행
let pollCount = 0;

export const handlers = [
  // POST /songs — 생성 요청
  http.post(`${API_BASE}/songs`, async () => {
    pollCount = 0;
    await delay(120);
    return HttpResponse.json<GenerateSongResponse>({
      generation_id: SAMPLE_GENERATION_ID,
      status: 'queued',
      estimated_seconds: 45,
      credit_cost: 1,
      credits_remaining: 41,
      subscribe_url: `/api/v1/events/${SAMPLE_GENERATION_ID}`,
    });
  }),

  // GET /songs/:id — 상태 조회 (폴링 fallback)
  http.get(`${API_BASE}/songs/:id`, async () => {
    pollCount += 1;
    await delay(80);
    if (pollCount >= 3) {
      return HttpResponse.json<GenerationStatusResponse>({
        generation_id: SAMPLE_GENERATION_ID,
        status: 'completed',
        progress: 100,
        credit_cost: 1,
        songs: SAMPLE_SONGS,
        lyrics:
          '[Verse 1]\n도시는 잠들지 않아\n새벽 세 시의 거리\n\n[Chorus]\nLet it rain, let it rain',
        license_pdf_url: 'https://cdn.music-maker.app/license/sample.pdf',
      } as GenerationStatusResponse);
    }
    const progress = Math.min(10 + pollCount * 30, 95);
    return HttpResponse.json<GenerationStatusResponse>({
      generation_id: SAMPLE_GENERATION_ID,
      status: 'processing',
      progress,
      stage: pollCount === 1 ? 'melody' : 'vocal_synthesis',
      started_at: new Date().toISOString(),
      estimated_remaining_s: Math.max(0, 45 - pollCount * 15),
    });
  }),

  // GET /events/:id — SSE (text/event-stream). MSW에서는 단발 stream으로 시뮬레이션.
  http.get(`${API_BASE}/events/:id`, () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        const events = [
          {
            event: 'progress',
            progress: 10,
            stage: 'lyrics_parsed',
            estimated_remaining_s: 40,
          },
          {
            event: 'progress',
            progress: 40,
            stage: 'melody',
            estimated_remaining_s: 27,
          },
          {
            event: 'progress',
            progress: 75,
            stage: 'vocal_synthesis',
            estimated_remaining_s: 11,
          },
          { event: 'completed', songs: SAMPLE_SONGS },
        ];
        for (const evt of events) {
          controller.enqueue(
            encoder.encode(`data: ${JSON.stringify(evt)}\n\n`),
          );
          await delay(500);
        }
        controller.close();
      },
    });
    return new HttpResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    });
  }),

  // GET /account/credits
  http.get(`${API_BASE}/account/credits`, () => {
    return HttpResponse.json<CreditsResponse>({
      credits: 42,
      plan: 'pro',
      plan_quota_per_month: 100,
      used_this_month: 58,
      renews_at: new Date(Date.now() + 14 * 86400_000).toISOString(),
      ledger_preview: [],
    });
  }),

  // GET /library
  http.get(`${API_BASE}/library`, () => {
    return HttpResponse.json<LibraryResponse>({
      items: [
        {
          id: '01HXG8A',
          generation_id: SAMPLE_GENERATION_ID,
          variant: 'A',
          title: 'Tokyo Rain - A',
          duration_ms: 90000,
          mp3_url: 'https://cdn.music-maker.app/s/A.mp3',
          cover_url: 'https://cdn.music-maker.app/c/A.jpg',
          is_favorite: true,
          tags: ['lofi', 'rain'],
          created_at: new Date().toISOString(),
        },
        {
          id: '01HXG8B',
          generation_id: SAMPLE_GENERATION_ID,
          variant: 'B',
          title: 'Tokyo Rain - B',
          duration_ms: 90000,
          mp3_url: 'https://cdn.music-maker.app/s/B.mp3',
          cover_url: 'https://cdn.music-maker.app/c/B.jpg',
          is_favorite: false,
          tags: ['lofi'],
          created_at: new Date().toISOString(),
        },
      ],
      next_cursor: null,
    });
  }),

  // POST /lyrics/generate
  http.post(`${API_BASE}/lyrics/generate`, async () => {
    await delay(400);
    return HttpResponse.json<LyricsGenerateResponse>({
      lyrics:
        '[Verse 1]\n도시는 잠들지 않아\n새벽 세 시의 거리\n\n[Chorus]\nLet it rain, let it rain\n비처럼 흘러 가도록',
      moderation: { flagged: false },
      credit_cost: 0,
    });
  }),
];
