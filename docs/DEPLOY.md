# Linktem 배포 가이드 (0원 인프라)

> 순서대로 진행. 각 단계에서 얻는 값(🔑)을 다음 단계에 넣는다.
> 비밀값은 **Render / Vercel / GitHub 대시보드에만** 입력하고 저장소·채팅에 남기지 않는다.

```
GitHub(private) ──push──▶ Render(API, Docker) ◀── UptimeRobot 5분 핑
      │                      │  ├─ Supabase(Postgres, Seoul)
      │                      │  ├─ Cloudflare R2(스틸컷) ──▶ 공개 URL
      │                      │  └─ Gemini API
      └──push──▶ Vercel(웹) ──브라우저가 Render 직접 호출(CORS)──┘
GitHub Actions(매일 03:00 KST) ──▶ POST /api/admin/cleanup
```

## 0. GitHub 저장소

1. private 저장소 `linktem` 생성 → `git remote add origin … && git push -u origin main`
2. Render·Vercel 이 이 저장소를 읽을 수 있도록 각 서비스에서 GitHub 앱 권한을 저장소 단위로 허용

## 1. Supabase (DB)

1. 새 프로젝트: Region **Northeast Asia (Seoul)**, DB 비밀번호는 비밀번호 관리자로 생성·보관
2. SQL Editor 에서 순서대로 실행
   - `apps/api/migrations/001_init.sql`
   - `apps/api/migrations/002_enable_rls.sql` (공개 REST API 로 테이블이 노출되지 않게 RLS 활성화)
3. Project Settings → Database → Connection string → **Transaction pooler (6543)** 복사
   🔑 `DATABASE_URL=postgresql://postgres.<ref>:<pw>@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres`
   - 비밀번호에 `@ : / ?` 등이 있으면 URL 인코딩 필요
4. 참고: 무료 프로젝트는 7일간 활동이 없으면 일시정지 → UptimeRobot 핑(§5)이 `/health` 만 치므로,
   실제 분석 요청이 뜸하면 대시보드에서 Restore 필요할 수 있음

## 2. Cloudflare R2 (스틸컷)

1. R2 → 버킷 `linktem` 생성 (Location: Automatic 또는 APAC)
2. 공개 접근: 버킷 Settings → **Custom Domain** 연결(도메인이 Cloudflare 에 있을 때, 예 `img.linktem.app`)
   또는 임시로 **R2.dev subdomain** 허용 (레이트 리밋 있음, 운영 비권장)
   🔑 `R2_PUBLIC_BASE_URL=https://img.linktem.app` (또는 `https://pub-xxxx.r2.dev`)
3. 버킷 CORS (오프라인 저장이 이미지를 fetch 로 받아 IndexedDB 에 넣음)
   ```json
   [{ "AllowedOrigins": ["https://linktem.vercel.app"], "AllowedMethods": ["GET", "HEAD"],
      "AllowedHeaders": ["*"], "MaxAgeSeconds": 86400 }]
   ```
   Vercel 도메인이 확정되면 그 주소로 교체(커스텀 도메인 추가 시 함께 등록)
4. R2 → Manage API Tokens → **Object Read & Write, 이 버킷만** 토큰 생성
   🔑 `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` (Secret 은 생성 시 한 번만 보임)

## 3. Gemini API

1. Google AI Studio → Get API key (결제 미연결 = 무료 티어)
   🔑 `GEMINI_API_KEY`
2. 모델: `gemini-3.8-flash` (2026-10 기준 무료 티어 Stable Flash, 영상·YouTube URL 입력 지원)
   - `gemini-2.0-flash` 는 2026-06-01 종료됨
   - 무료 티어 YouTube URL 입력은 하루 8시간 분량 제한, 무료 티어 데이터는 제품 개선에 사용될 수 있음
   - 한도 초과가 잦으면 `GEMINI_MODEL=gemini-3.5-flash-lite` 로 낮추거나 결제 연결
   - 실제 RPM/RPD 는 AI Studio → Rate limits 에서 확인

## 4. Render (API)

1. New → **Blueprint** → 저장소 선택 → `render.yaml` 인식 (서비스 `linktem-api`, Free, Singapore, Docker)
2. `sync: false` 항목 입력: `DATABASE_URL`, `GEMINI_API_KEY`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`,
   `R2_SECRET_ACCESS_KEY`, `R2_PUBLIC_BASE_URL`, (비워둬도 됨) `YTDLP_COOKIES_B64`
   - `ADMIN_TOKEN`, `CLIENT_HASH_SALT` 는 Render 가 자동 생성 → `ADMIN_TOKEN` 값은 §7 에서 사용
3. 첫 배포 로그에서 Docker 빌드 → `Linktem API 0.1.0 started (env=production, db=True)` 확인
4. 확인: `curl https://linktem-api.onrender.com/health` → `{"status":"ok",…}`
   🔑 API 주소 (서비스 이름이 이미 쓰이면 `linktem-api-xxxx.onrender.com` 처럼 달라짐)
5. 제약: 무료 인스턴스 512MB·0.1 CPU, 15분 무요청 시 슬립. YouTube 가 Render IP 를 봇으로 막으면
   로그에 `Sign in to confirm you're not a bot` → `YTDLP_COOKIES_B64`(쿠키 파일 base64) 또는 `YTDLP_PROXY` 설정

## 5. UptimeRobot

- HTTP(s) 모니터, `https://<api>/health`, 5분 간격 → 슬립 방지 (Render 무료 월 750시간 = 1개 서비스 상시 가동 가능)

## 6. Vercel (웹)

1. Add New Project → 저장소 선택 → **Root Directory: `apps/web`** (Framework: Next.js 자동)
   - `apps/web/vercel.json` 이 루트에서 `pnpm install --frozen-lockfile` 후 `@linktem/types` → 웹 순서로 빌드
2. Environment Variables (Production)
   | 변수 | 값 |
   | --- | --- |
   | `NEXT_PUBLIC_API_BASE_URL` | §4 의 API 주소 (브라우저 → Render 직접 호출, ADR-012) |
   | `NEXT_PUBLIC_SITE_URL` | `https://linktem.vercel.app` (실제 배포 주소) |
   | `NEXT_PUBLIC_DONATION_URL` | (선택) 후원 링크 |
   | `NEXT_PUBLIC_ADSENSE_CLIENT` | (승인 후) |
3. 배포 주소가 `linktem.vercel.app` 이 아니면 → Render `CORS_ORIGINS` 와 R2 CORS 를 실제 주소로 수정
   (프리뷰 `linktem-*.vercel.app` 은 API 가 정규식으로 허용)

## 7. GitHub Actions (만료 이미지 정리)

- Settings → Secrets and variables → Actions
  - `LINKTEM_API_URL` = API 주소, `LINKTEM_ADMIN_TOKEN` = Render 의 `ADMIN_TOKEN`
- Actions 탭 → image-cleanup → Run workflow 로 1회 수동 실행해 200 확인

## 8. 배포 후 점검

1. 폰에서 Vercel 주소 접속 → 홈 화면에 추가(PWA 설치)
2. 유튜브 쇼츠 링크 붙여넣기 → 1회차 분석(최대 1분+) → 카드·스틸컷 표시
3. 같은 링크 재입력 → 즉시 표시(캐시), 다른 기기에서 입력 → 회차 증가
4. Android: 유튜브 앱 [공유] → Linktem 선택 → 자동 분석 (Web Share Target)
5. 오프라인 저장 → 비행기 모드에서 리스트·이미지 확인
