import { create } from 'zustand';

export interface PlayerTrack {
  id: string;
  title: string;
  mp3Url: string;
  durationMs: number;
  coverUrl?: string;
}

interface PlayerStore {
  current: PlayerTrack | null;
  isPlaying: boolean;
  setTrack: (track: PlayerTrack | null) => void;
  play: () => void;
  pause: () => void;
  toggle: () => void;
}

export const usePlayerStore = create<PlayerStore>((set) => ({
  current: null,
  isPlaying: false,
  setTrack: (track) => set({ current: track, isPlaying: !!track }),
  play: () => set({ isPlaying: true }),
  pause: () => set({ isPlaying: false }),
  toggle: () => set((state) => ({ isPlaying: !state.isPlaying })),
}));
