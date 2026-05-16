# Music Maker (mureka-studio)

> 텍스트 한 줄로 보컬+반주가 포함된 BGM을 ~45초 안에 생성하는 AI 음원 SaaS.
> 자세한 비전/스펙: `docs/01-PRD.md`, `docs/02-UX-Design.md`, `docs/03-Architecture.md`.

## 빠른 시작 (Local)

```bash
make dev      # 전체 스택 기동 (postgres + redis + minio + api + worker + beat)
make migrate  # DB 마이그레이션
make test     # 백엔드 테스트
```

기본 포트:
- API: <http://localhost:8000> (`/docs` 에 OpenAPI UI)
- MinIO 콘솔: <http://localhost:9001>
- Postgres: localhost:5432, Redis: localhost:6379

`apps/web` (Next.js)은 별도 디렉토리에서 실행하세요. 현 PR 범위는 백엔드입니다.

## 모노레포 레이아웃

```
apps/
  api/        # FastAPI + Celery (이 PR)
  web/        # Next.js 15 (예정)
docs/
  01-PRD.md
  02-UX-Design.md
  03-Architecture.md
  adr/
docker-compose.yml
Makefile
```

## 핵심 제약

- `MUREKA_API_KEY` 는 **백엔드 전용**. 클라이언트/응답에 절대 노출 금지.
- Mureka API 는 비동기 (task_id 폴링) -> Celery 워커 + Redis pub/sub + SSE.
- 크레딧은 `credit_ledger` 가 진실 (Saga: hold -> charge | refund).

자세한 백엔드 가이드: [`apps/api/README.md`](apps/api/README.md).
