# Linktem (링크템) — 프로젝트 명세

> **링크 하나로 완성되는 스마트 장보기 리스트**
> 유튜브 · 인스타그램 · 틱톡의 "장보기/살림템/추천템" 영상 링크를 붙여넣거나 [공유하기]로 보내면,
> AI가 영상 속 상품을 찾아 **스틸컷 + 판매처 + 최저가 링크**가 붙은 체크리스트를 만들어 줍니다.
> 마트에서는 오프라인으로도 체크하며 장을 볼 수 있습니다.

---

## 1. 서비스 개요

| 항목 | 내용 |
| --- | --- |
| 서비스명 | Linktem (링크템) |
| 형태 | 모바일 우선 PWA (설치형 웹앱, Web Share Target 등록) |
| 핵심 가치 | 영상 → 장보기 체크리스트 자동 변환, 오프라인 장보기, 최저가 연결 |
| 수익 모델 | 구글 애드센스 배너, 개발자 후원 (쿠팡 파트너스는 사이트 게재 후 도입, ADR-013) |
| 비용 목표 | 월 0원 (전 구간 무료 티어) |

### 1.1 사용자 흐름

1. 사용자가 SNS 앱에서 [공유하기] → Linktem 선택 (또는 링크 직접 붙여넣기)
2. `/share` 가 공유 텍스트에서 URL을 추출해 홈(`/?url=...`)으로 넘김 → 자동 분석 시작
3. 분석 중에는 단계별 로딩 화면과 광고 플레이스홀더 노출
4. 결과: 아이템 카드 리스트 (스틸컷, 체크박스, 판매처 뱃지, 관련 영상 칩, "다른 제품이에요")
5. 여러 영상을 연달아 추가해 하나의 장보기 리스트로 누적 → [전체] [판매처별] [영상별] 탭으로 정리
6. "오프라인 장보기 저장" → IndexedDB 에 텍스트 + WebP 이미지 Blob 저장 → 마트 지하에서도 사용

---

## 2. 시스템 아키텍처 & 0원 인프라 맵

```
                ┌─────────────────────────── 사용자 (모바일 브라우저 / 설치된 PWA) ───────────────────────────┐
                │  Web Share Target(/share) · Service Worker(앱 셸 캐시) · IndexedDB(오프라인 리스트+이미지 Blob) │
                └───────────────┬──────────────────────────────────────────────────────────┬───────────────┘
                                │ HTTPS (정적/SSR)                                         │ <img> / fetch(blob)
                                ▼                                                          ▼
                ┌──────────────────────────────┐                          ┌─────────────────────────────────┐
                │ Vercel (Hobby, 무료)          │                          │ Cloudflare R2 (무료 10GB, egress 0)│
                │ apps/web — Next.js 14 App Router│                         │ captures/{video_id}/{item}.webp  │
                └───────────────┬──────────────┘                          └───────────────▲─────────────────┘
                                │ REST (JSON, CORS)                                       │ boto3 PutObject/DeleteObjects
                                ▼                                                         │
 ┌─────────────┐   GET /health  ┌──────────────────────────────────────────────────────────┴───────────────┐
 │ UptimeRobot │ ─────────────▶ │ Render (Free Web Service, Docker) — apps/api FastAPI                    │
 │ (5분 간격)   │  슬립 방지       │  yt-dlp(360p) → Gemini 3.8 Flash(JSON Schema) → ffmpeg 프레임 → Pillow WebP │
 └─────────────┘                └──────────────┬───────────────────────────────┬───────────────────────────┘
                                               │ asyncpg (Pooler 6543)          │ HTTPS
                                               ▼                                ▼
                                ┌──────────────────────────────┐   ┌──────────────────────────────┐
                                │ Supabase PostgreSQL (무료 500MB)│   │ Google Gemini API (무료 티어)   │
                                │ videos / products / video_items │   │ Files API + generateContent  │
                                │ image_lifecycle_logs / feedback │   └──────────────────────────────┘
                                └──────────────────────────────┘
```

| 구성요소 | 서비스 | 무료 한도 / 비용 방어 포인트 |
| --- | --- | --- |
| 프론트엔드 | Vercel Hobby | 정적 + 소량 SSR. API 호출은 브라우저 → Render 직접 (Vercel 함수 사용 0) |
| 백엔드 | Render Free (Docker) | 15분 무요청 시 슬립 → UptimeRobot 이 `/health` 5분 간격 핑 |
| 스토리지 | Cloudflare R2 | 10GB / 월 100만 Class A. Egress 무료. 이미지 30~50KB WebP 로 억제 |
| DB | Supabase Free | 500MB. 영상 원본 미저장, 메타데이터만 저장 |
| AI | Gemini 3.8 Flash | 무료 티어 RPM/RPD. **5회 앙상블 후 동결(Lock)** 으로 호출 상한 고정, URL 캐시 |

### 2.1 모노레포 구조

```
linktem/
├── docs/                 # PROJECT_SPEC.md, PROGRESS.md
├── packages/types/       # @linktem/types — 프론트/백엔드 공통 데이터 계약 (TypeScript)
├── apps/api/             # FastAPI + yt-dlp + ffmpeg + Gemini + R2 + Supabase(Postgres)
│   ├── app/
│   │   ├── main.py            # 라우터
│   │   ├── config.py          # 환경변수 (pydantic-settings)
│   │   ├── schemas.py         # @linktem/types 와 1:1 Pydantic 모델
│   │   ├── db.py              # asyncpg 풀
│   │   ├── repositories.py    # SQL 접근 계층
│   │   ├── rate_limit.py
│   │   └── services/
│   │       ├── url_utils.py       # URL 정규화 / 플랫폼 화이트리스트
│   │       ├── downloader.py      # yt-dlp 360p 다운로드
│   │       ├── gemini.py          # Gemini 구조화 추출
│   │       ├── image_processor.py # ffmpeg 캡처 + Pillow WebP
│   │       ├── storage.py         # R2 업로드/삭제
│   │       ├── ensemble.py        # 다수결 병합 (순수 함수)
│   │       └── analyzer.py        # 5회 점진적 앙상블 오케스트레이션
│   ├── migrations/001_init.sql
│   ├── tests/
│   └── Dockerfile
└── apps/web/             # Next.js 14 App Router + Tailwind + lucide-react + PWA
```

---

## 3. DB 테이블 스키마 (Supabase PostgreSQL)

원본 SQL: `apps/api/migrations/001_init.sql`

### 3.1 `videos` — 분석 대상 영상 (URL 캐시 키)

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | |
| platform | text | `youtube` / `instagram` / `tiktok` |
| canonical_key | text UNIQUE | 정규화 키 (예: `youtube:dQw4w9WgXcQ`) — 캐시 조회 키 |
| source_url | text | 정규화된 원본 URL |
| source_title | text | 영상 제목 |
| creator_name | text | 업로더/채널명 |
| duration_sec | int | 영상 길이 |
| analysis_count | int | 앙상블 회차 (1~5) — 고유 요청자 기준 |
| is_locked | bool | 5회차 도달 시 true → 이후 Gemini 호출 차단 |
| analysis_runs | jsonb | Gemini 회차별 원시 추출 결과 배열 (다수결 재계산용) |
| requester_hashes | text[] | 회차 카운트 중복 방지용 익명 클라이언트 해시 |
| images_expired | bool | 장기 미조회로 이미지가 정리됨 → 다음 요청 시 ffmpeg 만으로 복원 |
| last_requested_at | timestamptz | 이미지 TTL 판단 기준 |
| created_at / updated_at | timestamptz | |

### 3.2 `products` — 정규화된 상품 마스터 (영상 간 공유)

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | |
| normalized_key | text UNIQUE | `lower(name_en 영숫자/한글)` — 영상 간 동일 상품 매칭 (판매처 미포함, ADR-010) |
| name_ko / name_en | text | 한/영 상품명 |
| category | text | 카테고리 |
| retailer | text | 최초 발견 판매처 (대표값) |
| created_at / updated_at | timestamptz | |

### 3.3 `video_items` — 영상 × 상품 (체크리스트 아이템, `ShoppingItem.id`)

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | uuid PK | `ShoppingItem.id` |
| video_id | uuid FK → videos | ON DELETE CASCADE |
| product_id | uuid FK → products | |
| retailer | text | 이 영상에서의 판매처 (`ShoppingItem.retailer`) |
| timestamp_sec | numeric(8,2) | 캡처 타임스탬프 |
| image_key | text | R2 오브젝트 키 |
| image_url | text | 공개 URL (`R2_PUBLIC_BASE_URL/image_key`) |
| edition_note | text NULL | 한정판/용량/맛 등 에디션 메모 |
| vote_count | int | 앙상블 득표 수 |
| same_count / different_count | int | 사용자 피드백 집계 |
| is_hidden | bool | 피드백 임계치 초과 시 숨김 |
| position | int | 영상 내 등장 순서 |
| UNIQUE(video_id, product_id) | | |

### 3.4 `image_lifecycle_logs` — R2 이미지 수명주기 감사 로그

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | bigserial PK | |
| video_id | uuid NULL | |
| video_item_id | uuid NULL | 아이템 삭제 후에도 로그 보존 (FK 없음) |
| r2_key | text | |
| event | text | `UPLOADED` / `SUPERSEDED` / `DELETED` / `EXPIRED` / `RESTORED` |
| size_bytes | int NULL | |
| expires_at | timestamptz NULL | 이 시각 이후 정리 대상 (SUPERSEDED 유예기간) |
| processed_at | timestamptz NULL | 정리 완료 시각 |
| created_at | timestamptz | |

### 3.5 `user_feedback` — "다른 제품이에요" 피드백

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| id | bigserial PK | |
| video_item_id | uuid FK → video_items | ON DELETE CASCADE |
| feedback_type | text | `SAME` / `DIFFERENT` (CHECK) |
| client_hash | text | IP+UA 해시 (원문 미저장) |
| created_at / updated_at | timestamptz | |
| UNIQUE(video_item_id, client_hash) | | 1인 1표, 재투표 시 갱신 |

---

## 4. API 엔드포인트 명세 (apps/api)

Base URL: `https://<render-service>.onrender.com` · 모든 응답 JSON · 에러 형식 `{ "detail": string }`

### `POST /api/analyze`
영상 분석 및 캐시 반환 (5회 점진적 앙상블).

- Request — `VideoAnalysisRequest`
  ```json
  { "url": "https://www.youtube.com/shorts/abc123" }
  ```
- Response 200 — `VideoAnalysisResponse`
  ```json
  {
    "video_id": "6c1d…", "source_title": "이마트 장보기 하울", "creator_name": "살림채널",
    "source_url": "https://www.youtube.com/watch?v=abc123",
    "analysis_count": 2, "is_locked": false,
    "items": [{
      "id": "f3a…", "name_ko": "피코크 초마짬뽕", "name_en": "Peacock Choma Jjamppong",
      "category": "가공식품", "timestamp_sec": 42.5,
      "image_url": "https://img.linktem.app/captures/6c1d…/f3a….webp",
      "retailer": "이마트",
      "is_checked": false, "edition_note": "2인분"
    }]
  }
  ```
- 동작 규칙
  | 회차 | 동작 |
  | --- | --- |
  | 1 (최초) | 다운로드 → Gemini → 캡처 → R2 업로드 → **즉시 결과 반환** |
  | 2 ~ 4 | **캐시 즉시 반환** + BackgroundTask 로 추가 Gemini 분석 → 전 회차 다수결 병합/품질 보정 |
  | 5 | 캐시 반환 + 최종 다수결로 확정 후 `is_locked=true` (Gemini 호출 없음) |
  | 이후 | 캐시만 반환. Gemini 호출 영구 차단 |
  - 회차는 **고유 요청자(익명 해시) 기준**으로만 증가 (한 사람이 5번 눌러 조기 동결되는 것 방지)
  - 동일 URL 최초 분석이 동시에 들어오면 하나의 작업을 공유 (in-flight dedupe)
- 에러: `400` 지원하지 않는 URL · `413` 영상 길이 초과 · `422` 상품 미검출 · `429` 레이트 리밋 · `502` 다운로드/AI 실패

### `POST /api/feedback`
- Request — `UserFeedbackRequest` `{ "item_id": "f3a…", "feedback_type": "DIFFERENT" }`
- Response 200 — `UserFeedbackResponse` `{ "item_id": "f3a…", "same_count": 0, "different_count": 3, "is_hidden": true }`
- 규칙: 1인 1표(재투표 시 변경). `different_count ≥ FEEDBACK_HIDE_THRESHOLD` 이고 `different > same × 2` 이면 숨김.
  잠기지 않은 영상의 다음 앙상블 회차에서 감점 반영.

### `GET /api/videos/{video_id}/related`
"이 제품이 나온 다른 영상" 칩 데이터.
- Response 200 — `RelatedVideosResponse` `{ "items": { "<item_id>": [RelatedVideo, …] } }`
  `RelatedVideo = { video_id, source_title, creator_name, source_url }`

### `GET /health`
UptimeRobot 슬립 방지. DB 미의존(콜드 상태에서도 빠르게 200).
- Response 200 `{ "status": "ok", "version": "0.1.0", "time": "2026-10-23T02:00:00Z" }`

### `POST /api/admin/cleanup` (내부용)
- Header `X-Admin-Token: <ADMIN_TOKEN>`
- 만료 이미지 정리: (a) `SUPERSEDED` 유예기간 경과 이미지 삭제 (b) `IMAGE_TTL_DAYS` 동안 미조회 영상의 이미지 삭제 → `images_expired=true`
- Response `{ "superseded_deleted": n, "expired_videos": n, "expired_images": n }`

---

## 5. 공통 데이터 계약 (`packages/types` ↔ `app/schemas.py`)

| TypeScript (`@linktem/types`) | Pydantic (`app.schemas`) |
| --- | --- |
| `VideoAnalysisRequest` | `VideoAnalysisRequest` |
| `ShoppingItem` | `ShoppingItem` |
| `VideoAnalysisResponse` | `VideoAnalysisResponse` |
| `UserFeedbackRequest` / `FeedbackType` | `UserFeedbackRequest` / `FeedbackType` |
| `UserFeedbackResponse` | `UserFeedbackResponse` |
| `RelatedVideo` / `RelatedVideosResponse` | `RelatedVideo` / `RelatedVideosResponse` |
| `HealthResponse`, `ApiErrorResponse` | `HealthResponse`, (FastAPI 기본 `detail`) |

필드명은 snake_case 로 양쪽 동일, optional(`?`) ↔ `Optional[...] = None` 로 대응합니다.
`VideoAnalysisResponse.source_url` 은 명세 대비 **추가된 optional 필드**입니다 (ADR-007).

---

## 6. 외부 설정 체크리스트

- **Cloudflare R2 CORS** (오프라인 저장 시 브라우저가 이미지를 Blob 으로 fetch):
  ```json
  [{ "AllowedOrigins": ["https://linktem.vercel.app", "http://localhost:3000"],
     "AllowedMethods": ["GET", "HEAD"], "AllowedHeaders": ["*"], "MaxAgeSeconds": 86400 }]
  ```
- **R2 공개 접근**: 커스텀 도메인 또는 `r2.dev` 공개 URL → `R2_PUBLIC_BASE_URL`
- **Supabase**: SQL Editor 에서 `apps/api/migrations/001_init.sql` 실행, Connection Pooler(Transaction, 6543) URL → `DATABASE_URL`
- **UptimeRobot**: HTTP(s) 모니터, `https://<api>/health`, 5분 간격
- **cleanup 크론**: GitHub Actions `schedule` 등에서 하루 1회 `POST /api/admin/cleanup`
