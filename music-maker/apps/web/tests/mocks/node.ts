import { setupServer } from 'msw/node';
import { handlers } from './handlers';

/**
 * Node (Vitest) 환경 MSW 서버.
 */
export const server = setupServer(...handlers);
