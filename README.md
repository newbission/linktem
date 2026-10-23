# Linktem (링크템)

> 링크 하나로 완성되는 스마트 장보기 리스트 — SNS 장보기 영상 → AI 체크리스트 PWA

- 설계: [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md) · 진행 상태/ADR/환경변수: [`docs/PROGRESS.md`](docs/PROGRESS.md)

## 로컬 실행

```bash
# 0) 의존성
corepack enable   # 또는 npx pnpm@9.15.0 ...
pnpm install

# 1) API (Python 3.11+, ffmpeg 필요)
cd apps/api
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env   # DATABASE_URL, GEMINI_API_KEY, R2_* 입력
.venv/bin/uvicorn app.main:app --reload --port 8000

# 2) Web
cp apps/web/.env.example apps/web/.env.local
pnpm dev:web          # http://localhost:3000
```

## 테스트

```bash
cd apps/api && .venv/bin/python -m pytest
# 실제 Postgres 통합 테스트 — 테이블을 비우므로 앱 DB 와 분리된 전용 DB 사용 (이름에 "test" 없으면 skip)
# 최초 1회: docker exec linktem-db-1 psql -U postgres -c "create database linktem_test"
#          for f in migrations/*.sql; do docker exec -i linktem-db-1 psql -U postgres -d linktem_test < $f; done
TEST_DATABASE_URL=postgresql://postgres:linktem@127.0.0.1:54329/linktem_test .venv/bin/python -m pytest
pnpm --filter @linktem/web... run build
```
