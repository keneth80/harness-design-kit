# @music-maker/web

Music Maker — Next.js 15 (App Router) 프론트엔드.

## 로컬 실행

```bash
cd apps/web
pnpm install

# .env.local 작성 (.env.example 참고)
cp .env.example .env.local

# BE 미가동 환경에서도 MSW 모킹으로 자립 실행
pnpm dev
# → http://localhost:3000
```

### 환경 변수

| 변수 | 용도 |
|---|---|
| `NEXT_PUBLIC_API_BASE` | 자체 BE(FastAPI) 베이스 URL |
| `NEXT_PUBLIC_USE_MSW` | `true` 시 브라우저에서 MSW 모킹 활성 (BE 없이 개발) |
| `NEXTAUTH_SECRET` | NextAuth JWT 서명 키 |
| `NEXTAUTH_URL` | NextAuth callback URL |

### 금지된 환경변수 (보안)

- `NEXT_PUBLIC_MUREKA_*`, `NEXT_PUBLIC_OPENAI_*`, `NEXT_PUBLIC_STRIPE_*`
  모든 외부 API 키는 자체 BE(`apps/api`) 경유. 클라이언트 노출 절대 금지.

## 기술 스택

- Next.js 15 (App Router, RSC, Server Actions)
- TypeScript strict
- Tailwind CSS v3 + shadcn 패턴
- TanStack Query 5 + Zustand
- next-auth (credentials provider, mock)
- wavesurfer.js v7 (파형)
- react-hook-form + zod
- sonner (toast)
- framer-motion (마이크로 인터랙션)

## 디렉토리

```
apps/web/
├── app/                # App Router
│   ├── (marketing)/    # 랜딩
│   ├── (auth)/         # 로그인/가입
│   ├── (app)/          # 인증 후 영역 (Studio/Library/Settings)
│   └── api/auth/       # NextAuth route handler
├── components/
│   ├── ui/             # shadcn 컴포넌트
│   ├── studio/         # Studio 도메인
│   ├── library/
│   ├── shared/
│   └── layout/
├── lib/
│   ├── api/            # client, hooks, types, SSE
│   ├── store/          # zustand (generation, player)
│   └── utils/
└── tests/
    ├── unit/           # vitest + RTL
    ├── e2e/            # Playwright
    └── mocks/          # MSW handlers
```

## 테스트

```bash
pnpm test          # Vitest unit
pnpm test:e2e      # Playwright E2E (MSW 모킹)
pnpm typecheck     # tsc --noEmit
```

## MSW (Mock Service Worker)

BE(`apps/api`)가 아직 동작하지 않거나 빠른 UI 개발 시:

1. `.env.local`에 `NEXT_PUBLIC_USE_MSW=true`
2. 초기 1회 service worker 파일 생성: `npx msw init public/ --save`
3. `pnpm dev`

핸들러 위치: `tests/mocks/handlers.ts`

## 키보드 단축키 (Desktop)

- `Cmd/Ctrl + Enter` — Studio에서 생성 즉시 실행
- `Space` — 트랙 재생/정지 (입력 영역 외)

## 디자인 토큰

`02-UX-Design.md` 4.1 컬러 토큰을 `app/globals.css`의 CSS 변수로 매핑, Tailwind 토큰(`bg-canvas`, `text-foreground`, `bg-accent` 등)으로 노출.

다크 기본. `light` 클래스로 라이트 모드 전환 (next-themes).

## 접근성

- 모든 인터랙션 키보드 도달 가능, focus ring 2px accent
- 파형 플레이어: `aria-label`, `aria-valuenow` 동적 업데이트
- `prefers-reduced-motion` → 파동/회전 즉시 disable
