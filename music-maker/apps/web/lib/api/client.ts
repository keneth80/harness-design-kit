import type { ApiProblem } from './types';

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  constructor(
    public problem: ApiProblem,
    public status: number,
  ) {
    super(problem.title || 'API error');
    this.name = 'ApiError';
  }
}

interface FetchOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  /** JWT — 클라이언트 측에서는 next-auth getSession()로 주입 */
  token?: string | null;
  /** Idempotency key (POST 멱등성) */
  idempotencyKey?: string;
}

function generateTraceId(): string {
  // 짧은 trace id (서버에서 RFC 4122 ULID 생성)
  return Math.random().toString(36).slice(2, 12);
}

/**
 * 타입 안전한 fetch wrapper.
 * - JWT 자동 첨부
 * - X-Trace-Id 헤더
 * - RFC 7807 에러 처리
 */
export async function apiFetch<T>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const { body, token, idempotencyKey, headers, ...rest } = options;

  const finalHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Trace-Id': generateTraceId(),
    ...(headers as Record<string, string> | undefined),
  };
  if (token) {
    finalHeaders.Authorization = `Bearer ${token}`;
  }
  if (idempotencyKey) {
    finalHeaders['Idempotency-Key'] = idempotencyKey;
  }

  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...rest,
      headers: finalHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (networkError) {
    // 네트워크 오류 — 백엔드 미가동 등
    throw new ApiError(
      {
        type: 'about:blank',
        title: 'Network error',
        status: 0,
        detail:
          networkError instanceof Error
            ? networkError.message
            : 'Failed to reach server',
      },
      0,
    );
  }

  if (!response.ok) {
    let problem: ApiProblem;
    try {
      problem = (await response.json()) as ApiProblem;
    } catch {
      problem = {
        type: 'about:blank',
        title: response.statusText || 'Request failed',
        status: response.status,
      };
    }
    throw new ApiError(problem, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export { API_BASE };
