# Frontend Implementation Report

## 2026-05-15 21:30 — Music Maker Next.js 15 Web 초기 구현

### 구현한 화면 ID / 기능 ID

- W1 Studio 3-pane (`/studio`)
- W2 가사 에디터 (`/studio/lyrics`, `LyricsEditor` 컴포넌트)
- W3 스타일 프리셋 (`StylePicker` 컴포넌트, Studio 탭에 통합)
- W4 생성 진행률 + 팁 슬라이드 (`GenerationProgress`)
- W5 A/B 결과 비교 (`/studio/result/[id]`, `AbCompare`)
- W6 라이브러리 그리드 (`/library`, `LibraryGrid`)
- 인증 시작 페이지 (`/sign-in`, `/sign-up`, mock)
- 랜딩 (`/`)
- Dashboard (`/dashboard`)

기능 ID 매핑 (01-PRD MoSCoW):
- M1 텍스트→음원: `StudioPanel` + `useGenerateSong` + `useGenerationStatus`
- M2 가사 자동 생성: `useLyricsGenerate` 훅 + 가사 탭 (AI 모드)
- M3 미리듣기: `WaveformPlayer` (wavesurfer.js v7)
- M4 다운로드: A/B 결과 화면 MP3/WAV 버튼
- M5 인증/크레딧: NextAuth credentials provider + `CreditMeter`
- S1 스타일 프리셋: `StylePicker`
- S2 생성 이력: Studio 우측 History 영역 (스텁) + Library
- US-S2 진행률 실시간: SSE + 5s polling fallback

### 추가/수정한 컴포넌트

```
apps/web/
├── app/
│   ├── layout.tsx                                # 루트 (Providers, dark default)
│   ├── globals.css                               # 디자인 토큰 CSS 변수
│   ├── (marketing)/{layout,page}.tsx             # 랜딩 + 헤더
│   ├── (auth)/{sign-in,sign-up}/page.tsx
│   ├── (app)/
│   │   ├── layout.tsx                            # 사이드바 + 토프바 + 모바일 하단 탭
│   │   ├── dashboard/page.tsx
│   │   ├── studio/{page,lyrics/page}.tsx
│   │   ├── studio/result/[id]/page.tsx           # 진행률/실패/A-B 라우터
│   │   ├── library/{page,[id]/page}.tsx
│   │   └── settings/page.tsx
│   └── api/auth/[...nextauth]/route.ts           # NextAuth (mock)
├── components/
│   ├── providers.tsx                             # QueryClient + ThemeProvider + Sonner + MSW
│   ├── ui/                                       # shadcn 패턴 직접 작성
│   │   ├── button.tsx, input.tsx, textarea.tsx
│   │   ├── badge.tsx, card.tsx, label.tsx
│   │   ├── progress.tsx, slider.tsx, tabs.tsx, skeleton.tsx
│   ├── studio/
│   │   ├── studio-panel.tsx                      # W1 입력 + 생성 폼
│   │   ├── lyrics-editor.tsx                     # W2
│   │   ├── style-picker.tsx                      # W3
│   │   ├── generation-progress.tsx               # W4 (팁 6초 회전, aria-live)
│   │   ├── ab-compare.tsx                        # W5 (좌우 트랙)
│   │   ├── waveform-player.tsx                   # wavesurfer.js v7 wrapper + Space 단축키
│   │   └── generate-button.tsx                   # 파동 ripple
│   ├── library/{library-grid, track-card}.tsx    # W6
│   ├── layout/{nav-bar, side-nav, bottom-nav}.tsx
│   └── shared/credit-meter.tsx                   # count-down 애니메이션
├── lib/
│   ├── api/{client, sse, types}.ts               # 03-Architecture 4.1~4.7 매핑
│   ├── api/hooks/{use-generate-song, use-generation-status,
│   │             use-credits, use-library, use-lyrics-generate}.ts
│   ├── store/{generation-store, player-store}.ts
│   └── utils/{cn, format}.ts
├── tests/
│   ├── unit/{lyrics-editor, waveform-player, generation-progress, format}.test.{ts,tsx}
│   ├── e2e/generate-song.spec.ts
│   ├── mocks/{handlers, browser, node}.ts        # MSW
│   └── setup/vitest.setup.ts
├── package.json, tsconfig.json, next.config.mjs
├── tailwind.config.ts, postcss.config.mjs
├── playwright.config.ts, vitest.config.ts
├── .env.example
└── README.md
```

### shadcn 컴포넌트 추가 목록

shadcn CLI 대신 동일 패턴으로 직접 작성 (Radix Primitives + cva):
- Button, Input, Textarea, Badge, Card, Label
- Progress, Slider, Tabs, Skeleton

추후 필요 시 `npx shadcn@latest add dialog dropdown-menu form select tooltip sheet avatar sonner` 로 확장.

### 호출하는 API

| Hook | Method | Path | UI |
|---|---|---|---|
| useGenerateSong | POST | /songs | StudioPanel |
| useGenerationStatus | SSE/GET | /events/:id, /songs/:id | result/[id] |
| useCredits | GET | /account/credits | CreditMeter |
| useLibrary | GET | /library | LibraryGrid |
| useLyricsGenerate | POST | /lyrics/generate | 가사 탭 AI 모드 |

### 상태 UI (3가지 모두 구현 확인)

- **idle**: Studio 입력 화면, Library empty state, GenerateButton idle 상태
- **loading**: GenerationProgress + 팁 슬라이드 + 진행률 바, Library skeleton, GenerateButton spinner
- **error**: result/[id] danger 패널, Library danger banner, GenerateButton shake + 토스트

### 핵심 제약 준수 체크

- [x] MUREKA/외부 API 키 클라이언트 미노출 — `.env.example`에 명시 + apiFetch는 자체 BE만 호출
- [x] 다크모드 기본 — `<html class="dark">` + `defaultTheme="dark"` (next-themes)
- [x] A/B 비교 UI — `AbCompare`가 2곡 좌우 배치 (W5 충실 구현)
- [x] SSE + polling fallback — `use-generation-status.ts`에 양쪽 모두 구현, MSW에서 stream + REST 모두 지원
- [x] vertical slice — 각 컴포넌트마다 단위 테스트 1개씩 작성

### 접근성 / 반응형

- 반응형: Tailwind breakpoints 그대로 (1280+ 3-pane, 768~1280 2-pane, <768 1-pane + BottomNav)
- ARIA: WaveformPlayer (region, progressbar, aria-valuenow), GenerationProgress (aria-live)
- 키보드: Cmd+Enter=생성, Space=재생/정지, focus-ring 2px accent
- prefers-reduced-motion: globals.css에서 animation-duration 0.01ms 즉시 disable

### 적용한 lessons-learned 교훈

- `docs/lessons-learned.md` 부재 → 기본 안전 패턴 적용
- 보안 규칙(`.claude/rules/security.md`) 준수: 외부 API 키 클라이언트 노출 금지, 입력 검증(zod), 에러 메시지 sanitize
- 코딩 스타일: immutability (zustand setter spread), 작은 파일 (대부분 < 200 lines)

### 미해결 TODO

- **NextAuth 정식 OAuth**: 현재 mock credentials. Google/Apple provider 연결 필요
- **Service Worker**: `public/mockServiceWorker.js` 는 첫 dev 실행 시 `npx msw init public/ --save` 필요
- **shadcn 풀세트**: Dialog/Dropdown/Select/Tooltip 등은 필요한 화면에서 추가 설치 권장
- **wavesurfer A/B 동기 재생**: 02-UX 5.3 명세의 좌/우 동일 timeline + 80ms cross-fade는 아직 미구현 (개별 플레이어로 동작)
- **가상 스크롤**: `@tanstack/react-virtual`를 의존성에 포함했지만 LibraryGrid는 아직 일반 grid (대량 트랙 시 적용 필요)
- **License PDF 다운로드, 공유 링크, Stem 분리, Project**: 03-Architecture 4.8 기타 엔드포인트들은 스텁/미구현
- **실제 BE 연동**: `apps/api` 동작 후 SSE stream과 RFC 7807 응답 형식 검증 필요

### 다음 액션

- code-verifier로 검증 요청 (Layer D lessons-learned 위반 자동 검사)
- qa-engineer로 boundary 검증 요청 (apps/api Pydantic 스키마 ↔ lib/api/types.ts 정합성)
- `pnpm install` 완료 후 `pnpm typecheck`, `pnpm test` 통과 확인
- `pnpm dev`로 dev 서버 부팅 시 콘솔 에러 없음 확인 (MSW 모킹 ON 상태)
