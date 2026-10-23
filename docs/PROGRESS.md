# Linktem — 진행 상태 (PROGRESS)

> 세션 기록(요청·결정·발견한 문제): [`SESSION_LOG.md`](SESSION_LOG.md)

## Current Phase

**전 단계 완료 — 배포 준비 단계**

완료: Step 0, Step 1, Step 2, Step 3

---

## Step 0. 프로젝트 문서화 기반 구축

- [x] `docs/PROJECT_SPEC.md` — 서비스 개요, 0원 인프라 맵, DB 스키마, API 명세
- [x] `docs/PROGRESS.md` — Step 0~3 태스크 리스트 초기화

## Step 1. 모노레포 뼈대 및 packages/types

- [x] 루트 `package.json`, `pnpm-workspace.yaml`, `.gitignore`, `.editorconfig`, `.nvmrc`
- [x] `packages/types/package.json`, `tsconfig.json`
- [x] `packages/types/src/index.ts` — 공통 데이터 계약 (+ `UserFeedbackResponse`, `RelatedVideo(s)`, `HealthResponse`, `SHOPPING_CATEGORIES`)
- [x] `pnpm --filter @linktem/types build` 빌드 검증 (dist/index.js, index.d.ts 생성 확인)

## Step 2. 백엔드 (apps/api)

- [x] `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`(pytest 설정), `.env.example`
- [x] `app/config.py` — 환경변수 (pydantic-settings)
- [x] `app/schemas.py` — @linktem/types 1:1 Pydantic 모델
- [x] `migrations/001_init.sql` — Supabase 스키마 (5개 테이블 + 트리거 + RLS)
- [x] `app/db.py`, `app/repositories.py` — asyncpg 데이터 계층
- [x] `app/services/url_utils.py` — URL 정규화 / 플랫폼 화이트리스트(SSRF 방지)
- [x] `app/services/downloader.py` — yt-dlp `bv*[height<=360]+ba/…/wv*+wa/w`, 길이 사전 검사
- [x] `app/services/gemini.py` — Gemini 3.8 Flash, JSON Schema 구조화 출력, 유튜브 URL 직접 입력 + Files API 폴백
- [x] `app/services/image_processor.py` — ffmpeg ±0.4초 3프레임 중 최선명 선택 → 720p WebP q75 (목표 ≤50KB)
- [x] `app/services/storage.py` — R2 업로드 / 일괄 삭제 / 만료 이미지 정리
- [~] ~~`app/services/affiliate.py` — 쿠팡 파트너스 딥링크~~ → 사이트 게재 후 재도입하기로 하고 제거 (ADR-013)
- [x] `app/services/ensemble.py` — 다수결 병합 (클러스터링/득표/피드백 감점)
- [x] `app/services/analyzer.py` — 5회 점진적 앙상블 & 캐시 & Lock, in-flight dedupe, 이미지 복원
- [x] `app/rate_limit.py`, `app/main.py` — `/api/analyze`, `/api/feedback`, `/api/videos/{id}/related`, `/health`, `/api/admin/cleanup`
- [x] `Dockerfile`(python:3.11-slim + ffmpeg + deno), `.dockerignore`, 루트 `render.yaml`, `.github/workflows/image-cleanup.yml`
- [x] `tests/` — 단위 47개 통과 (url_utils / ensemble / image_processor / 계약 / API / sync plan)
- [x] `tests/test_integration_db.py` — 실제 PostgreSQL 대상 1→5회차 Lock·피드백·관련영상·만료/복원 3개 통과
- [x] 실제 yt-dlp 스모크 테스트 (YouTube 19초 영상 → 476KB 다운로드 → WebP 10KB 캡처)
- [x] `docker build --platform linux/amd64` 성공 → 컨테이너 `/health` 200, HEALTHCHECK healthy, ffmpeg 7.1 / deno 2.8.3 / 비루트 사용자 확인, 컨테이너 안에서 실제 YouTube 다운로드 + WebP 캡처 성공
- [ ] (미검증) 실제 Gemini / R2 API 호출 — 키 미보유. 가짜 구현으로 흐름만 검증

## Step 3. 프론트엔드 (apps/web)

- [x] Next.js 14.2 App Router + Tailwind 3.4 + lucide-react 세팅 (`next.config.mjs`, `tailwind.config.ts`, `vercel.json`)
- [x] 헤더 "Linktem" 브랜드 텍스트 + 온라인/오프라인 표시 + PWA 설치 버튼 (`Header.tsx`)
- [x] 링크 입력창(붙여넣기 버튼, 지원 플랫폼 사전 검증) + 단계별 분석 로딩 화면 + 애드센스 300×250 / 320×100 플레이스홀더
- [x] 아이템 카드: 스틸컷(타임스탬프 점프), 체크박스, 판매처 뱃지, 관련 영상 칩, "다른 제품이에요"(되돌리기)
- [x] 탭 필터 [전체 보기] [판매처별] [영상별] — 체크한 항목은 아래로, 영상별 그룹에 AI 검증 n/5 · 확정 뱃지
- [x] 장보기 진행률 / 체크 초기화 / 전체 지우기, 리스트는 localStorage 영속
- [x] IndexedDB 오프라인 저장 (`idb`): 텍스트 스냅샷 + WebP Blob, `navigator.storage.persist()`, 체크 상태 자동 동기화
- [x] PWA: `public/manifest.json`(share_target GET → `/share`), `public/sw.js`(앱 셸 캐시), 아이콘(any/maskable/apple)
- [x] `/share` — title/text/url 에서 URL 추출 → `/?url=` 자동 분석
- [x] 분석 UX 개선: `/health` 로 서버 상태를 먼저 확인하고 응답이 없으면 '서버 깨우는 중' 단계로 최대 75초 대기(`waitForServer`), 분석 도중 연결이 끊기면 1회 재시도,
  분석 중 버튼 스피너 + 리스트 잠금(pointer-events/inert), 입력한 링크는 성공 시에만 비움, 클립보드 권한 거부 시 에러 대신 붙여넣기 안내
- [x] 로컬 전체 스택 `docker-compose.yml` (db+api+web) + `apps/web/Dockerfile`(standalone) — 서버 깨우기 시나리오 검증 (API 중지 상태에서 분석 시작 → 12초 뒤 API 기동 → 자동으로 분석 이어짐)
- [x] 같은 출처 API 프록시(`app/api/[...path]`, `app/health` → `API_PROXY_TARGET`): Tailscale/LAN 등 localhost 가 아닌 주소로 접속 시 API 연결 실패 문제 해결, 사용자 IP 를 X-Forwarded-For 로 전달
- [x] 로딩 문구 단일화(서버 연결 대기도 '분석 중' 흐름, 15초 이상이면 안내 한 줄), 내 리스트에 이미 있는 영상(공유 형태 무관)은 서버 호출 없이 즉시 표시
- [x] 리스트 내보내기 (`ExportListPanel`, `lib/export.ts`): 판매처별 ☐/☑ 텍스트 복사 + Web Share API 공유, 옵션 [남은 항목만]
- [x] 푸터: AI 결과 안내 + 후원 링크(`NEXT_PUBLIC_DONATION_URL`, 비우면 숨김). 쿠팡 대가성 고지는 ADR-013 으로 제거
- [x] `pnpm --filter @linktem/web... build` + `next lint` 통과 (/ 106kB First Load)
- [x] E2E 확인: 외부 서비스만 가짜로 바꾼 실제 API + 로컬 Postgres + `next start` → 공유 URL 진입 → 자동 분석 → 리스트/관련 영상 칩 렌더링, 390px 모바일 뷰포트 가로 오버플로 없음
- [x] E2E 중 발견한 버그 수정: 판매처가 다르면 같은 상품도 관련 영상으로 연결되지 않던 문제 (ADR-010)
- [ ] (미검증) 실기기에서 PWA 설치 후 SNS 앱 [공유하기] 목록 노출 — HTTPS 배포 후 Android Chrome 에서 확인 필요
  (iOS Safari 는 Web Share Target 미지원 → 링크 붙여넣기 사용)

## 배포 체크리스트

> 단계별 상세: [`DEPLOY.md`](DEPLOY.md)

- [x] git 저장소 초기화 + 첫 커밋 (2026-10-23)
- [ ] GitHub private 저장소 생성 + push
- [ ] Supabase 프로젝트 생성 → `001_init.sql`, `002_enable_rls.sql` 실행 → Pooler URL 확보
- [ ] Cloudflare R2 버킷 `linktem` + 공개 도메인 + CORS (PROJECT_SPEC §6) + API 토큰
- [ ] Render: `render.yaml` Blueprint 로 서비스 생성, `sync: false` 환경변수 입력, 첫 배포에서 `docker build` 확인
- [ ] UptimeRobot: `https://<api>/health` 5분 간격
- [ ] Vercel: Root Directory `apps/web`, `NEXT_PUBLIC_API_BASE_URL` 등 설정
- [ ] GitHub secrets `LINKTEM_API_URL`, `LINKTEM_ADMIN_TOKEN` (image-cleanup 워크플로)

## 향후 확장 계획

1. **인스타그램 사진(캐러셀) 게시글** — 영상이 없는 게시물은 이미지들을 Gemini 에 직접 넣어 분석 (현재는 400 응답)
2. **작업 큐 분리** — 사용량 증가 시 BackgroundTask → Upstash QStash/Redis 큐 + 워커, advisory lock 으로 다중 인스턴스 대응 (ADR-005)
3. **분석 진행 상황 스트리밍** — SSE 로 다운로드/AI/캡처 단계 실시간 표시 (현재는 체감 진행률)
4. **상품 매칭 고도화** — 임베딩 기반 동일 상품 클러스터링, 바코드/가격표 OCR 로 에디션 구분
5. **쿠팡 파트너스 재도입 (사이트 게재 후, 한 번에)** — ADR-013 체크리스트 참고. 이후 멀티 제휴(이마트몰, 컬리, 올리브영), 가격 비교 위젯
6. **계정 없는 기기 간 동기화** — 공유 코드/QR 로 리스트 공유 (가족 장보기), Supabase Realtime
7. **애드센스 승인 후** `AdSlot` 을 `<ins class="adsbygoogle">` 로 교체, 결과 화면 인피드 광고
8. **관리자 화면** — 피드백 많은 아이템 검수, 동결 영상 재분석(Lock 해제) 도구
9. **iOS 대응** — 단축어(Shortcuts) 레시피로 공유 시트 → Linktem 열기

---

---

## 아키텍처 결정사항 (ADR)

### ADR-001. 패키지 매니저: pnpm workspace
- 결정: pnpm 9 workspace (`apps/*`, `packages/*`). `packageManager` 필드로 버전 고정.
- 이유: Vercel 이 pnpm 모노레포를 네이티브 지원, 디스크/설치 속도 우위, `--filter <pkg>...` 로 의존 패키지(types) 선빌드 가능.

### ADR-002. 공통 계약은 TypeScript 가 원본(Source of Truth)
- 결정: `packages/types/src/index.ts` 가 원본, Python `app/schemas.py` 는 이를 1:1 미러링하고
  `tests/test_contract.py` 가 TS 파일을 파싱해 필드명/optional 여부 일치를 검증.
- 이유: 코드 생성 도구(추가 의존성) 없이 계약 드리프트를 CI 에서 잡을 수 있음.

### ADR-003. DB 접근: supabase-py 대신 asyncpg 직접 연결
- 결정: Supabase Postgres 에 Connection Pooler(transaction mode, 6543)로 asyncpg 접속, `statement_cache_size=0`.
- 이유: 아이템 동기화(UPSERT/DELETE/로그)를 **하나의 트랜잭션**으로 묶고 `SELECT … FOR UPDATE` 로 회차 카운트를
  원자적으로 올려야 함. PostgREST(supabase-py)로는 다중 테이블 트랜잭션이 불가능. 동기 HTTP 클라이언트 블로킹도 회피.
- 영향: 모든 테이블 RLS 활성 + 정책 없음 → anon 키로는 접근 불가, 백엔드만 접근.

### ADR-004. 회차(analysis_count)는 고유 요청자 기준
- 결정: IP+UA 솔트 해시가 처음 보이는 경우에만 회차 증가 (`videos.requester_hashes`, 최근 50개 유지).
- 이유: 한 사용자가 새로고침 5번으로 1~2개 샘플만으로 조기 동결시키는 것을 방지. 원문 IP 는 저장하지 않음.

### ADR-005. Gemini 호출 상한 = 4회, 5회차는 동결 전용
- 결정: 1회차(동기) + 2~4회차(BackgroundTask) = Gemini 최대 4회. 5회차 요청 시 즉시 `is_locked=true`,
  백그라운드에서 진행 중인 4회차를 영상별 Lock 으로 기다린 뒤 **피드백 감점 포함 최종 다수결**만 수행(신규 상품 추가 없음).
- 채택 기준: `votes - 피드백감점 ≥ ceil(회차/2)` → 2회차 합집합, 3회차 이상 과반.
- 동시성: 영상별 `asyncio.Lock` + 최초 분석 in-flight 공유. Render Free 는 단일 인스턴스이므로 충분.
  수평 확장 시 Postgres advisory lock(session pooler) 또는 작업 큐로 교체 필요.

### ADR-006. 아이템 ID 안정성 & 이미지 수명주기
- 결정: 새 회차 결과를 기존 아이템과 상품 키/유사도로 매칭해 UPDATE (ID 유지 → 클라이언트 체크 상태 보존).
  타임스탬프가 3초 이상 바뀔 때만 재캡처.
- 교체/제거된 이미지는 즉시 지우지 않고 `SUPERSEDED` + `expires_at`(기본 7일) 기록 → 오프라인 저장본/열린 화면 보호.
- 90일 미조회 영상은 이미지를 정리하고 `images_expired=true`; 다음 요청 시 ffmpeg 만으로 복원(Gemini 0회).
- R2 키에 랜덤 접미사 → 불변 URL, `Cache-Control: immutable` 1년.

### ADR-007. 계약 확장: `VideoAnalysisResponse.source_url?`, 피드백/관련영상 응답 타입
- 결정: 명세 타입은 그대로 두고 optional `source_url` 과 `UserFeedbackResponse`, `RelatedVideo(s)Response` 를 추가.
- 이유: "영상에서 보기"(타임스탬프 점프), "이 제품이 나온 다른 영상" 칩 클릭 시 재분석에 원본 URL 필요.

### ADR-008. 유튜브는 Gemini URL 직접 입력 + 다운로드 병렬
- 결정: 유튜브는 Gemini 에 공개 URL 을 `file_data` 로 넘기고, 캡처용 360p 다운로드를 동시에 진행.
  실패 시 다운로드한 mp4 를 Files API 로 업로드해 재시도. 인스타/틱톡은 항상 업로드 경로.
- 이유: 업로드 대기 시간 제거로 1회차 응답 속도 개선.
- 주의: Render 데이터센터 IP 는 YouTube 봇 차단 대상이 될 수 있음 → `YTDLP_COOKIES_B64`, `YTDLP_PROXY` 지원.
  yt-dlp 의 YouTube 추출에 필요한 Deno 런타임을 Docker 이미지에 포함.

### ADR-009. 다운로드는 360p, 캡처는 "짧은 변 ≤720px(확대 없음)"
- 결정: 명세의 "360p 다운로드"와 "720p 캡처"를 함께 만족시키기 위해 캡처는 720p 를 상한으로 두고 업스케일하지 않음.
  ±0.4초 3프레임 중 엣지 분산이 가장 큰(가장 선명한) 프레임을 채택.

### ADR-010. 상품 키에서 판매처 제외, 판매처는 영상별 아이템에 저장
- 결정: `products.normalized_key = normalize(name_en)`, 판매처는 `video_items.retailer` 에 저장해 `ShoppingItem.retailer` 로 응답.
  `products.retailer` 는 최초 발견 판매처(대표값)로만 사용.
- 이유: E2E 중 "이마트 영상의 비비고 왕교자"와 "코스트코 영상의 비비고 왕교자"가 서로 다른 상품이 되어
  "이 제품이 나온 다른 영상" 칩이 비는 문제 발견. 회귀 테스트 `test_related_videos_match_across_retailers` 추가.

### ADR-011. 프론트 상태: localStorage(텍스트) + IndexedDB(오프라인 스냅샷·이미지)
- 결정: 리스트/체크/피드백은 localStorage 에 즉시 저장, "오프라인 장보기 저장" 시 IndexedDB 에 스냅샷 + 이미지 Blob.
  이후 체크 변경은 스냅샷에 자동 반영, 영상/이미지 구성이 바뀌면 "다시 저장" 버튼으로 안내.
- 이미지는 Vercel Image Optimization 대신 `<img>` 로 R2 직접 로드 (무료 한도 방어), 저장된 Blob 이 있으면 object URL 우선 사용.
- 앱을 열 때 미동결 영상 최대 3개를 조용히 재요청해 백그라운드 앙상블 개선분을 반영 (같은 사용자는 회차 증가 없음).

### ADR-012. 브라우저 → 같은 출처 `/api` → Next 프록시 → API (기본값)
- 문제: 번들에 `http://localhost:8000` 이 박혀 Tailscale 등 다른 기기에서 접속하면 그 기기 자신의 localhost 로 요청해 실패.
  Next `rewrites` 는 사용자 IP(X-Forwarded-For)를 붙이지 않아 레이트 리밋·1인 1표가 프록시 IP 하나로 뭉침.
- 결정: Route Handler 프록시(`lib/server/api-proxy.ts`)로 헤더 화이트리스트, 사용자 IP 전달, 180초 타임아웃을 직접 제어.
  `API_PROXY_TARGET` 은 런타임 환경변수라 이미지 재빌드 없이 바꿀 수 있음. `NEXT_PUBLIC_API_BASE_URL` 을 넣으면 직접 호출로 전환.
- Vercel: Hobby 플랜 함수 실행 시간 제한 때문에 1회차 분석(최대 1분+)이 프록시에서 끊길 수 있으므로,
  운영에서는 `NEXT_PUBLIC_API_BASE_URL=https://<render>` 로 직접 호출(CORS 설정 완료)을 권장.
- 서버 쪽 캐시: 이미 분석된 영상은 Gemini 미설정이어도 즉시 반환 (`test_cached_video_served_without_ai`).

### ADR-013. 쿠팡 파트너스 기능 전부 제거, 사이트 게재 후 한 번에 재도입
- 배경: 파트너스 승인에는 게재된 사이트가 필요하고, 키 없이는 일반 검색 링크(수수료 없음)와 대가성 고지만 노출되어 의미가 없음.
- 제거한 것: `services/affiliate.py`, `Settings.coupang_*`, `Analyzer._fill_affiliates`, `repo.products_without_affiliate / set_affiliate_url`,
  `products.affiliate_url` 컬럼(001_init.sql), `ShoppingItem.affiliate_url`(TS·Pydantic), 카드의 "쿠팡 최저가 확인" 버튼,
  내보내기 [쿠팡 링크 포함] 옵션, 푸터·리스트 상단 대가성 고지, env 예시·`render.yaml` 의 `COUPANG_*`.
- 유지한 것: 판매처 라벨 "쿠팡"(영상에서 쿠팡 구매라고 한 경우의 retailer 값, ensemble 정규화·뱃지 색상) — 제휴와 무관.
- 재도입 체크리스트: ① 새 마이그레이션 `002_affiliate.sql` 로 `products.affiliate_url text` 추가 ② 계약에 `affiliate_url?` 추가 + 계약 테스트
  ③ Open API 딥링크(HMAC-SHA256 `CEA algorithm=HmacSHA256, access-key=…, signed-date=…, signature=…`, `POST /v2/providers/affiliate_open_api/apis/openapi/v1/deeplink`)
  결과를 products 에 캐시, 실패 시 링크 숨김 ④ 카드 버튼 `rel="sponsored"` ⑤ 공정위 대가성 고지(푸터 + 링크가 보이는 화면, 내보내기 텍스트)
  ⑥ `COUPANG_ACCESS_KEY / SECRET_KEY / SUB_ID` 를 env 예시·render.yaml 에 추가.
- 로컬 docker DB 에는 기존 `products.affiliate_url` 컬럼이 남아 있어도 코드가 참조하지 않으므로 무해 (`docker compose down -v` 로 초기화 가능).

## 환경변수 템플릿

### apps/api (`apps/api/.env.example`)

| 변수 | 예시 / 기본값 | 설명 |
| --- | --- | --- |
| `APP_ENV` | `production` | production 이면 `/docs` 비활성 |
| `CORS_ORIGINS` | `https://linktem.vercel.app,http://localhost:3000` | 쉼표 구분 |
| `ADMIN_TOKEN` | `openssl rand -hex 32` | `/api/admin/cleanup` 보호 |
| `CLIENT_HASH_SALT` | `openssl rand -hex 16` | 익명 요청자 해시 솔트 |
| `DATABASE_URL` | `postgresql://postgres.<ref>:<pw>@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres` | Supabase Pooler |
| `GEMINI_API_KEY` | | Google AI Studio |
| `GEMINI_MODEL` | `gemini-3.8-flash` | |
| `GEMINI_USE_YOUTUBE_URL` | `true` | ADR-008 |
| `MAX_VIDEO_DURATION_SEC` | `1200` | 20분 |
| `YTDLP_PROXY` / `YTDLP_COOKIES_B64` | | 봇 차단/로그인 대응 |
| `STORAGE_BACKEND` | `auto` / `local` / `r2` | auto: R2 키 있으면 R2, 없으면 로컬 |
| `LOCAL_STORAGE_DIR` / `LOCAL_STORAGE_PUBLIC_PATH` | `./data/media` / `/media` | 로컬 저장 위치, 서빙 경로 |
| `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | | R2 API 토큰 (Object Read & Write) |
| `R2_BUCKET` | `linktem` | |
| `R2_PUBLIC_BASE_URL` | `https://img.linktem.app` | 커스텀 도메인 또는 r2.dev |
| `IMAGE_SUPERSEDED_GRACE_DAYS` / `IMAGE_TTL_DAYS` | `7` / `90` | ADR-006 |
| `ENSEMBLE_MAX_RUNS` / `FEEDBACK_HIDE_THRESHOLD` | `5` / `3` | |
| `ANALYZE_RATE_LIMIT_PER_MIN` | `6` | IP 당 |

### apps/web (`apps/web/.env.example`)

| 변수 | 예시 | 설명 |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | (비움) 또는 `https://linktem-api.onrender.com` | 비우면 같은 출처 프록시, 넣으면 직접 호출 (Vercel 운영 권장) |
| `API_PROXY_TARGET` | `http://localhost:8000` / `http://api:8000` | 프록시 대상 (런타임 env) |
| `NEXT_PUBLIC_SITE_URL` | `https://linktem.vercel.app` | 메타데이터/OG |
| `NEXT_PUBLIC_DONATION_URL` | `https://buymeacoffee.com/<id>` | 비우면 후원 링크 숨김 |
| `NEXT_PUBLIC_ADSENSE_CLIENT` | `ca-pub-XXXX` | 승인 후 설정 |

GitHub Actions secrets: `LINKTEM_API_URL`, `LINKTEM_ADMIN_TOKEN` (image-cleanup 워크플로)
