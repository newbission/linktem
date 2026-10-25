# Linktem — 개발 세션 기록

> 2026-10-23 첫 개발 세션(Claude Code)에서 오간 요청, 결정, 검증 결과를 시간순으로 정리한 문서입니다.
> 단계별 체크리스트와 ADR 원문은 [`PROGRESS.md`](PROGRESS.md), 설계는 [`PROJECT_SPEC.md`](PROJECT_SPEC.md) 를 참고하세요.

---

## 1. 최초 요청

"SNS 영상/게시글 장보기 체크리스트 자동 생성 PWA" **Linktem** 을 모노레포로 구축.

- `docs/` 실시간 문서화 (PROJECT_SPEC, PROGRESS)
- `packages/types` 공통 계약 → `apps/api` (FastAPI, yt-dlp, ffmpeg, Gemini, R2, Supabase) → `apps/web` (Next.js 14 PWA)
- 0원 인프라: Vercel + Render(Docker) + Cloudflare R2 + Supabase, UptimeRobot `/health`
- 5회 점진적 앙상블 (1회차 즉시 / 2~4회차 백그라운드 다수결 / 5회차 동결)

## 2. 진행 순서와 결과

### Step 0 — 문서
- `PROJECT_SPEC.md`: 서비스 개요, 인프라 맵, DB 5개 테이블, API 명세
- `PROGRESS.md`: Step 0~3 체크리스트, ADR, 환경변수 템플릿

### Step 1 — 모노레포 / 타입
- pnpm 9 workspace, `@linktem/types` (TS 가 계약 원본, Python 은 미러 + 계약 테스트)

### Step 2 — 백엔드
- 서비스: `url_utils`(정규화·SSRF 방지), `downloader`(360p), `gemini`(JSON Schema), `image_processor`(3프레임 중 최선명 → 720p WebP),
  `storage`(R2), `affiliate`(쿠팡 딥링크 — 이후 제거, 10장), `ensemble`(다수결), `analyzer`(앙상블 오케스트레이션)
- DB: supabase-py 대신 **asyncpg 직접 연결** (다중 테이블 트랜잭션 필요, ADR-003)
- 검증: 단위 테스트 + 실제 PostgreSQL 통합 테스트, 실제 YouTube 다운로드 → WebP 캡처

### Step 3 — 프론트엔드
- 입력/로딩/광고 플레이스홀더, 아이템 카드, 탭 3종, IndexedDB 오프라인 저장, manifest(Web Share Target), SW, 공정위 고지 푸터
- E2E (외부 서비스만 가짜, 실제 API + Postgres + next start) 로 공유 → 분석 → 리스트 흐름 확인

## 3. 세션 중 발견한 문제와 수정

| # | 발견 | 원인 | 조치 |
| --- | --- | --- | --- |
| 1 | 관련 영상 칩이 비어 있음 | 상품 키에 판매처 포함 → 이마트/코스트코의 같은 상품이 다른 상품 | 상품 키는 이름만, 판매처는 `video_items.retailer` (ADR-010) |
| 2 | "Docker 꺼져 있다"고 보고 | Docker Desktop 본체 미실행(헬퍼만 실행) | Docker 실행 후 `docker build` + 컨테이너 내부 실제 다운로드까지 검증 |
| 3 | 체크만 해도 "오프라인 다시 저장" 표시 | 저장 시각 비교 | 이미지 구성 시그니처 비교로 변경 |
| 4 | "서버에 연결할 수 없어요" | **Tailscale 로 외부 접속** 시 번들의 `localhost:8000` 이 접속 기기 자신을 가리킴 | 같은 출처 `/api` → Next Route Handler 프록시 (ADR-012) |
| 5 | rewrite 프록시 사용 시 모든 사용자 IP 동일 | Next rewrites 가 X-Forwarded-For 미부착 | 직접 만든 프록시로 사용자 IP 전달 |
| 6 | "클립보드 접근이 허용되지 않았어요" 빨간 에러 | Chrome 사이트별 클립보드 권한 거부 | 입력창 포커스 + 붙여넣기 안내, 미지원 브라우저는 버튼 숨김 |
| 7 | 분석 누르면 링크가 사라짐 / 중복 조작 가능 | 제출 즉시 입력 초기화, 잠금 없음 | 성공 시에만 비움, 버튼 스피너 + 리스트 잠금(inert) |
| 8 | "잠든 서버를 깨우고 있어요" 문구 어색 | — | 하나의 '분석 중' 흐름으로, 15초 이상이면 안내 한 줄 |

## 4. 사용자 결정 / 피드백 요약

- 로딩 화면: "자고 있어요" 같은 표현 대신 **그냥 분석 중**으로 표시
- 분석 중에는 **조작 잠금**, 입력한 링크는 **유지**
- **이미 등록된 링크는 바로 보여주기** → 내 리스트에 있으면 서버 호출 없이 표시, 서버 DB 캐시는 AI 키 없이도 반환
- **리스트 외부 복사/공유** 기능 추가 (판매처별 ☐/☑ 텍스트, 남은 항목만, 쿠팡 링크 포함 시 대가성 문구 자동 첨부)
- 외부 접속은 **Tailscale** 로 함 → localhost 하드코딩 금지

## 5. 쿠팡 파트너스 링크 논의

- 현재: Open API 키가 있으면 상품명별 "쿠팡 검색 결과" 파트너스 링크를 자동 생성해 DB 캐시, 없으면 일반 검색 링크(수수료 없음)
- "내 파트너스 링크 하나로 대체"는 고정 링크 하나가 한 페이지로만 가므로 '최저가 확인' 이 상품과 무관해져 비권장
- 진행: 파트너스 대시보드에서 Open API 키 발급 → Render 환경변수 `COUPANG_ACCESS_KEY` / `COUPANG_SECRET_KEY` 입력 (코드 변경 없음)
- 발급 조건(최종 승인, 실적 기준 등)은 대시보드에서 확인 필요

## 6. 검증 현황 (세션 종료 시점)

| 항목 | 결과 |
| --- | --- |
| API 단위 + 통합 테스트 | 52개 통과 (`TEST_DATABASE_URL` 지정 시 통합 포함) |
| `pnpm --filter @linktem/web... build` / `next lint` | 통과 |
| `docker build` (linux/amd64) | 성공, `/health` 200, HEALTHCHECK healthy, ffmpeg 7.1 / deno 2.8.3 |
| 컨테이너 내부 실제 YouTube 다운로드 + WebP 캡처 | 성공 (476KB → 10KB) |
| docker compose 전체 스택 | db/api/web 기동, localhost · Tailscale IP 양쪽 접속 확인 |
| 실제 Gemini / R2 API | **미검증** (키 없음) |
| 실기기 PWA 설치 후 공유 목록 노출 | **미검증** (HTTPS 배포 후 Android Chrome 에서 확인) |

## 7. 로컬 실행 상태

```bash
docker compose up -d --build      # http://localhost:3000 또는 http://<tailscale-ip>:3000
# 실제 분석: apps/api/.env 에 GEMINI_API_KEY=... 추가 후
docker compose up -d api
```

- Compose 프로젝트 이름은 폴더명과 무관하게 `linktem` 으로 고정 (`docker-compose.yml` 의 `name:`)
- DB: `localhost:54329` (postgres / linktem), 마이그레이션 자동 적용

## 7-1. 로컬 환경변수 파일

- `apps/api/.env`, `apps/web/.env.local` 생성 (git 제외, 권한 600). 템플릿은 각 폴더의 `.env.example`
- 채워 둔 값: 로컬 DB(`localhost:54329`), `ADMIN_TOKEN`·`CLIENT_HASH_SALT`(랜덤 생성), 나머지 기본값
- 비어 있는 값(직접 입력): `GEMINI_API_KEY`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_PUBLIC_BASE_URL`,
  (선택) `YTDLP_PROXY`, `YTDLP_COOKIES_B64`
- docker compose 의 api 컨테이너는 `apps/api/.env` 를 읽되 `DATABASE_URL`·`CORS_ORIGINS`·`APP_ENV` 는 compose 값으로 덮어씀
- 운영 값은 파일이 아니라 Render / Vercel 대시보드에 입력 (Supabase Pooler URL 등)
- 환경별 실제 값 파일(`.env.production`)은 만들지 않음: 운영 비밀값은 대시보드에만 두어 유출·커밋 위험 제거.
  대신 대시보드에 옮길 체크리스트로 `apps/api/.env.production.example`, `apps/web/.env.production.example` (값 없음, git 포함)
- 서버/프론트 분리 원칙: 비밀값은 `apps/api/.env` 에만. `NEXT_PUBLIC_*` 는 브라우저에 노출되므로 공개해도 되는 값만

## 7-2. 로컬 스틸컷 저장소

- `STORAGE_BACKEND=auto|local|r2` (기본 auto: R2 키가 있으면 R2, 없으면 로컬 디스크), `LOCAL_STORAGE_DIR`(기본 `./data/media`)
- 로컬 저장 시 API 가 `/media` 로 서빙(1년 immutable 캐시), 응답 URL 은 상대 경로 `/media/...` → 웹 `/media` 프록시로 어떤 접속 주소에서도 표시
- docker compose: `media` 볼륨(`/app/data/media`)에 보존. slim 이미지의 `.webp` MIME 누락 문제 수정

## 8. 다음 할 일

1. `apps/api/.env` 에 `GEMINI_API_KEY` 넣고 실제 영상으로 분석 품질 확인 (프롬프트·카테고리 튜닝)
2. Cloudflare R2 버킷 + CORS + 공개 도메인 → 스틸컷 확인
3. 배포: Supabase → Render(`render.yaml`) → Vercel(운영은 `NEXT_PUBLIC_API_BASE_URL` 로 Render 직접 호출 권장) → UptimeRobot
4. (사이트 게재 후) 쿠팡 파트너스 승인 → ADR-013 체크리스트대로 한 번에 재도입
5. Android 실기기에서 PWA 설치 → SNS [공유하기] 동작 확인

## 9. 폴더 이름 변경 메모 (eurecart → linktem)

- Claude Code 세션 기록은 `~/.claude/projects/-Users-jm-development-projects-eurecart/` 에 경로 기준으로 저장됨
  → 폴더 이름을 바꾼 뒤 이 디렉터리도 `-Users-jm-development-projects-linktem` 으로 바꾸면 `claude --resume` 으로 이어서 사용 가능
- `apps/api/.venv` 는 절대 경로가 박혀 있으므로 이름 변경 후 재생성 권장
  (`rm -rf apps/api/.venv && python3 -m venv apps/api/.venv && apps/api/.venv/bin/pip install -r apps/api/requirements-dev.txt`)

## 10. 쿠팡 파트너스 기능 제거 (2026-10-23)

- 사용자 결정: "쿠팡 연결 전까지는 관련된 거 없애자. 나중에 만들고 한 번에 추가"
- 백엔드·프론트·계약·DB 스키마·env·render.yaml 에서 제휴 링크와 대가성 고지를 모두 제거. 판매처 라벨 "쿠팡"은 유지
- 재도입 방법은 PROGRESS.md ADR-013 체크리스트에 기록
- 검증: API 테스트 56개(통합 포함) 통과, web typecheck·lint·build 통과
- 함께 논의 중: 스틸컷을 썸네일(256p q60, 약 10KB) + 확대용(720p q45, 약 31KB) 두 장으로 나누는 안 — 사용자 확인 대기

## 11. 같은 제품 연결 떼기 · README 재작성 · GitHub 공개 (2026-10-24)

- README 를 일반 사용자 눈높이로 재작성: 애니메이션 SVG 4개(`docs/assets`, `generate_svgs.py` 로 재생성) + Mermaid 4개, 개발자 안내는 접기 섹션
- GitHub 공개 저장소 생성·푸시: https://github.com/newbission/linktem (이력에 비밀값 없음 확인)
- 사용자 결정: 제보 기준 등 정확한 수치는 공개 문서에서 숨김 → '일정 수 이상'으로 표기, 운영 값은 대시보드 환경변수 (DEPLOY.md §4)
- 연결 떼기(ADR-018): 다른 영상 칩의 × → 즉시 숨김 + 서버 기록, 기기 저장본 `unlinked` 로 IP 가 바뀌어도 유지
- 검증: API 테스트 77개(통합 포함) 통과, web typecheck·lint·build 통과, 프록시 경유 `/api/related/unlink` 응답 확인
  (앱 DB 에 같은 제품이 겹치는 영상이 없어 화면에서 실제 떼기는 아직 못 해 봄)
- 별도 커밋: 계정 기능 준비로 `PyJWT[crypto]` 의존성 추가 (아직 코드에서 사용 안 함)
