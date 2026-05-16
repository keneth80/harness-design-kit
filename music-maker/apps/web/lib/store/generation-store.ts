import { create } from 'zustand';
import type { GenerationStatus, SongPublic } from '@/lib/api/types';

export interface ActiveGeneration {
  id: string;
  status: GenerationStatus;
  progress: number;
  stage: string;
  estimatedRemainingS: number;
  startedAt: string;
  songs?: SongPublic[];
  error?: { code: string; message: string };
}

interface GenerationStore {
  active: Record<string, ActiveGeneration>;
  upsert: (gen: ActiveGeneration) => void;
  remove: (id: string) => void;
  get: (id: string) => ActiveGeneration | undefined;
}

export const useGenerationStore = create<GenerationStore>((set, getState) => ({
  active: {},
  upsert: (gen) =>
    set((state) => ({
      active: { ...state.active, [gen.id]: gen },
    })),
  remove: (id) =>
    set((state) => {
      const { [id]: _omit, ...rest } = state.active;
      return { active: rest };
    }),
  get: (id) => getState().active[id],
}));
