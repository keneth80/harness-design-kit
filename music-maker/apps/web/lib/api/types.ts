/**
 * docs/03-Architecture.md 섹션 4 API 명세와 1:1 매칭되는 TS 타입.
 * Pydantic 스키마 자동 생성으로 대체될 예정 (현재는 수동 작성).
 */

export type GenerationMode = 'song' | 'instrumental' | 'tts';
export type LyricsMode = 'user' | 'ai' | 'none';
export type MurekaModel = 'mureka-7' | 'mureka-o1';
export type GenerationStatus =
  | 'queued'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'cancelled';
export type SongVariant = 'A' | 'B';

export interface Prompt {
  text: string;
  length_s: number;
  genres: string[];
  moods: string[];
  bpm?: number;
  key?: string;
  instruments?: string[];
}

export interface GenerateSongRequest {
  mode: GenerationMode;
  prompt: Prompt;
  lyrics?: string | null;
  lyrics_mode: LyricsMode;
  model: MurekaModel;
  preset_id?: string | null;
  project_id?: string | null;
}

export interface GenerateSongResponse {
  generation_id: string;
  status: GenerationStatus;
  estimated_seconds: number;
  credit_cost: number;
  credits_remaining: number;
  subscribe_url: string;
}

export interface SongPublic {
  id: string;
  variant: SongVariant;
  mp3_url: string;
  wav_url: string;
  duration_ms: number;
  bpm: number;
  key: string;
  genres: string[];
  moods: string[];
  cover_url: string;
}

export interface GenerationProcessing {
  generation_id: string;
  status: 'processing' | 'queued';
  progress: number;
  stage: string;
  started_at: string;
  estimated_remaining_s: number;
}

export interface GenerationCompleted {
  generation_id: string;
  status: 'completed';
  progress: 100;
  credit_cost: number;
  songs: SongPublic[];
  lyrics?: string;
  license_pdf_url?: string;
}

export interface GenerationFailed {
  generation_id: string;
  status: 'failed' | 'cancelled';
  error_code: string;
  error_message: string;
  refunded: number;
}

export type GenerationStatusResponse =
  | GenerationProcessing
  | GenerationCompleted
  | GenerationFailed;

// SSE Events (docs 5.3)
export type GenerationEvent =
  | { event: 'queued'; position: number }
  | {
      event: 'progress';
      progress: number;
      stage: string;
      estimated_remaining_s?: number;
    }
  | { event: 'retrying'; attempt: number }
  | { event: 'completed'; songs: SongPublic[] }
  | { event: 'failed'; error: string; refunded: number }
  | { event: 'ping' };

// Lyrics
export interface LyricsGenerateRequest {
  topic: string;
  language: 'ko' | 'en';
  tone: 'emotional' | 'energetic' | 'cinematic' | 'playful';
  structure?: ('verse' | 'chorus' | 'bridge' | 'outro' | 'hook')[];
  syllables_per_line?: number;
}

export interface LyricsGenerateResponse {
  lyrics: string;
  moderation: { flagged: boolean; reason?: string };
  credit_cost: number;
}

// Library
export interface LibraryItem {
  id: string;
  generation_id: string;
  variant: SongVariant;
  title: string;
  duration_ms: number;
  cover_url?: string;
  mp3_url: string;
  is_favorite: boolean;
  tags: string[];
  created_at: string;
}

export interface LibraryResponse {
  items: LibraryItem[];
  next_cursor: string | null;
}

// Credits
export interface CreditsResponse {
  credits: number;
  plan: 'free' | 'pro' | 'studio';
  plan_quota_per_month: number;
  used_this_month: number;
  renews_at: string;
  ledger_preview: {
    type: 'hold' | 'charge' | 'refund' | 'grant' | 'purchase';
    amount: number;
    reason: string;
    at: string;
  }[];
}

// RFC 7807 Problem+JSON
export interface ApiProblem {
  type: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
  trace_id?: string;
}
