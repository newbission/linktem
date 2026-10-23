import type {
  AnalyzeResponse,
  ApiErrorResponse,
  RelatedVideosResponse,
  UserFeedbackRequest,
  UserFeedbackResponse,
  VideoAnalysisRequest,
  VideoLookupResponse,
} from '@linktem/types';

/**
 * 비워 두면 같은 출처(/api/*, /health)로 요청하고 Next 서버가 API_PROXY_TARGET 으로 프록시한다 (기본).
 * → localhost·Tailscale IP·도메인 등 어떤 주소로 접속해도 동작하고 CORS 가 필요 없다.
 * 값을 넣으면 브라우저가 그 주소의 API 를 직접 호출한다.
 */
export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? '').replace(/\/+$/, '');
const API_LABEL = API_BASE_URL || '이 사이트의 /api';

// 분석은 서버 백그라운드 작업으로 돌고 요청은 작업 접수만 하므로 짧게 끝난다 (콜드 스타트는 waitForServer 가 흡수)
const ANALYZE_TIMEOUT_MS = 30_000;
const DEFAULT_TIMEOUT_MS = 20_000;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(
  path: string,
  init: RequestInit & { timeoutMs?: number } = {},
): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal, ...rest } = init;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new DOMException('timeout', 'TimeoutError')), timeoutMs);
  const onAbort = () => controller.abort(signal?.reason);
  signal?.addEventListener('abort', onAbort);

  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(rest.headers ?? {}) },
    });
    if (!res.ok) {
      let detail = `요청에 실패했어요 (${res.status})`;
      try {
        const body = (await res.json()) as Partial<ApiErrorResponse>;
        if (typeof body.detail === 'string') detail = body.detail;
      } catch {
        /* JSON 이 아닌 에러 본문 */
      }
      throw new ApiError(detail, res.status);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (signal?.aborted) throw new ApiError('분석을 취소했어요.', 499);
    if (controller.signal.aborted) {
      throw new ApiError('응답이 너무 오래 걸려요. 잠시 후 다시 시도해 주세요.', 408);
    }
    throw new ApiError(`분석 서버(${API_LABEL})에 연결할 수 없어요.`, 0);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onAbort);
  }
}

const HEALTH_TIMEOUT_MS = 5_000;
const WAKE_POLL_INTERVAL_MS = 3_000;
// Render 무료 인스턴스 콜드 스타트는 보통 30~60초
const WAKE_MAX_WAIT_MS = 75_000;

async function pingHealth(signal?: AbortSignal): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
  const onAbort = () => controller.abort();
  signal?.addEventListener('abort', onAbort);
  try {
    const res = await fetch(`${API_BASE_URL}/health`, { signal: controller.signal, cache: 'no-store' });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onAbort);
  }
}

/**
 * 서버가 응답할 때까지 대기 (슬립 상태의 무료 서버 깨우기).
 * 첫 핑이 실패하면 onWaking 을 호출하고 주기적으로 재시도한다. 끝내 실패하면 ApiError(status 0).
 */
export async function waitForServer(options: { signal?: AbortSignal; onWaking?: () => void } = {}): Promise<void> {
  const { signal, onWaking } = options;
  if (await pingHealth(signal)) return;
  onWaking?.();
  const deadline = Date.now() + WAKE_MAX_WAIT_MS;
  while (Date.now() < deadline) {
    if (signal?.aborted) throw new ApiError('분석을 취소했어요.', 499);
    await new Promise((r) => setTimeout(r, WAKE_POLL_INTERVAL_MS));
    if (await pingHealth(signal)) return;
  }
  if (signal?.aborted) throw new ApiError('분석을 취소했어요.', 499);
  console.error(`[Linktem] API 서버 응답 없음: ${API_BASE_URL || window.location.origin}/health`);
  throw new ApiError(
    `분석 서버(${API_LABEL})에 연결할 수 없어요. 서버가 꺼져 있거나 브라우저 확장 프로그램이 요청을 막고 있을 수 있어요.`,
    0,
  );
}

/** 이미 분석된 영상이면 video, 처음 보는 영상이면 job (진행 상황은 getJob 으로 조회) */
export function analyzeVideo(url: string, signal?: AbortSignal): Promise<AnalyzeResponse> {
  const body: VideoAnalysisRequest = { url };
  return request<AnalyzeResponse>('/api/analyze', {
    method: 'POST',
    body: JSON.stringify(body),
    signal,
    timeoutMs: ANALYZE_TIMEOUT_MS,
  });
}

/** 분석 작업 진행 상황 (완료 시 video 포함). 폴링용이라 서버 레이트 리밋 대상이 아니다. */
export function getJob(jobId: string): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>(`/api/jobs/${encodeURIComponent(jobId)}`, { cache: 'no-store' });
}

/** 리스트에 있는 영상들의 최신 결과 (회차를 올리지 않는 조회 전용) */
export function lookupVideos(videoIds: string[]): Promise<VideoLookupResponse> {
  return request<VideoLookupResponse>(`/api/videos?ids=${encodeURIComponent(videoIds.join(','))}`, {
    cache: 'no-store',
  });
}

export function sendFeedback(body: UserFeedbackRequest): Promise<UserFeedbackResponse> {
  return request<UserFeedbackResponse>('/api/feedback', { method: 'POST', body: JSON.stringify(body) });
}

export function fetchRelated(videoId: string): Promise<RelatedVideosResponse> {
  return request<RelatedVideosResponse>(`/api/videos/${encodeURIComponent(videoId)}/related`);
}
