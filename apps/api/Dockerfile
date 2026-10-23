# Linktem API — Render Docker 배포용
# yt-dlp 의 YouTube 추출은 외부 JS 런타임(Deno)이 필요하므로 공식 이미지에서 바이너리만 복사한다.
FROM denoland/deno:bin-2.8.3 AS deno

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

# ffmpeg: 프레임 캡처 + yt-dlp video/audio 머지 (필수)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deno /deno /usr/local/bin/deno

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY migrations ./migrations

# 로컬 저장소(STORAGE_BACKEND=local) 기본 위치 — compose 에서 볼륨으로 마운트
RUN mkdir -p /app/data/media \
    && useradd --create-home --uid 10001 linktem && chown -R linktem:linktem /app
USER linktem

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=4)"

# Render 는 PORT 환경변수를 주입한다. 512MB 메모리이므로 워커 1개 + asyncio 동시성으로 처리.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 75"]
