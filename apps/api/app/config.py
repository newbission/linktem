"""환경변수 기반 설정. 템플릿은 apps/api/.env.example 참고."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- 앱 ---
    app_env: str = "development"
    # 쉼표 구분 문자열 (예: https://linktem.vercel.app,http://localhost:3000)
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:3000"])
    admin_token: str = ""
    # 클라이언트 해시(1인 1표, 회차 중복 방지)에 섞는 비밀 값
    client_hash_salt: str = "linktem-dev-salt"

    # --- Supabase PostgreSQL ---
    database_url: str = ""
    db_pool_min: int = 1
    db_pool_max: int = 5

    # --- Gemini ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_temperature: float = 0.2
    gemini_timeout_sec: int = 180
    # 추론(thinking) 단계 — 상품명/시점 추출은 깊은 추론이 필요 없어 낮출수록 빠르다. 빈 값이면 모델 기본값
    gemini_thinking_level: Literal["", "minimal", "low", "medium", "high"] = "low"
    # 영상 프레임 해상도 — low 는 프레임당 토큰이 약 1/4 (포장 글씨 정도는 식별 가능)
    gemini_media_resolution: Literal["low", "medium", "high"] = "low"
    # 유튜브는 Gemini 가 URL 을 직접 읽게 하고 다운로드는 캡처용으로 병렬 진행
    gemini_use_youtube_url: bool = True

    # --- yt-dlp ---
    max_video_duration_sec: int = 1200
    download_timeout_sec: int = 180
    # 이 길이 이하 영상은 720p 로 받아 확대용 스틸컷 화질 확보 (긴 영상은 360p — 용량/시간 절약)
    download_hd_max_duration_sec: int = 180
    ytdlp_proxy: str = ""
    # Netscape cookies.txt 를 base64 로 인코딩한 값 (인스타그램 로그인 필요 게시물 대응)
    ytdlp_cookies_b64: str = ""

    # --- 이미지 ---
    # 확대용: 짧은 변 720px, WebP q45 (실측: 작은 성분표 글씨까지 판독, 약 30KB)
    image_max_short_side: int = 720
    image_webp_quality: int = 45
    image_target_max_bytes: int = 50 * 1024
    image_min_quality: int = 35
    # 리스트 카드 썸네일: 화면 84px(3배율 기기 약 250px) → 짧은 변 256px, q60 (약 10KB)
    image_thumb_short_side: int = 256
    image_thumb_quality: int = 60
    # AI 시점 기준 후보 프레임 오프셋(초). 환경변수는 JSON 배열: IMAGE_CANDIDATE_OFFSETS=[-1,-0.5,0,0.5,1]
    image_candidate_offsets: list[float] = [-1.0, -0.5, 0.0, 0.5, 1.0]
    # 후보 중 제품이 보이는 프레임을 고르는 경량 모델 (별도 무료 한도). 비우면 선명도만으로 선택
    frame_selection_model: str = "gemini-3.5-flash-lite"
    frame_selection_timeout_sec: int = 60

    # --- 스틸컷 저장소 ---
    # auto: R2 자격 증명이 있으면 r2, 없으면 local / local: 디스크 / r2: Cloudflare R2
    storage_backend: Literal["auto", "local", "r2"] = "auto"
    # local 저장 위치 (상대 경로는 실행 위치 기준). Docker 에서는 /app/data/media 볼륨
    local_storage_dir: str = "./data/media"
    # local 이미지 URL 접두어 (API 가 이 경로로 서빙, 웹은 같은 경로를 API 로 프록시)
    local_storage_public_path: str = "/media"

    # --- Cloudflare R2 ---
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "linktem"
    r2_public_base_url: str = ""
    # 교체된 이미지를 실제 삭제하기까지의 유예 (오프라인 저장본/열린 화면 보호)
    image_superseded_grace_days: int = 7
    # 이 기간 동안 아무도 요청하지 않은 영상의 이미지는 정리 (다음 요청 시 복원)
    image_ttl_days: int = 90

    # --- 앙상블 ---
    ensemble_max_runs: int = 5
    feedback_hide_threshold: int = 3
    # '사진이 달라요' 제보가 이만큼 모이면 사진을 내리고 더 넓은 구간에서 다시 고른다
    image_report_threshold: int = 2

    # --- 레이트 리밋 ---
    analyze_rate_limit_per_min: int = 6

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def r2_endpoint_url(self) -> str:
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    @property
    def r2_configured(self) -> bool:
        return bool(self.r2_account_id and self.r2_access_key_id and self.r2_secret_access_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
