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
# 실제 Postgres 통합 테스트 (migrations/001_init.sql 적용된 빈 DB, 테이블을 비움)
TEST_DATABASE_URL=postgresql://... .venv/bin/python -m pytest tests/test_integration_db.py
pnpm --filter @linktem/web... run build
```
