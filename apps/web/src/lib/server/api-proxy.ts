import 'server-only';

/**
 * 같은 출처 API 프록시: 브라우저 → (이 사이트) /api/*, /health, /media/* → API_PROXY_TARGET.
 * - 어떤 주소(localhost, Tailscale IP, 도메인)로 접속해도 API 호출이 동작하고 CORS 가 필요 없다.
 * - 실제 사용자 IP 를 X-Forwarded-For 로 넘겨 API 의 레이트 리밋 / 1인 1표가 프록시 IP 로 뭉치지 않게 한다.
 * - API_PROXY_TARGET 은 런타임 환경변수 (빌드 후에도 변경 가능)
 */
const FORWARD_REQUEST_HEADERS = ['content-type', 'accept', 'accept-language', 'user-agent', 'x-admin-token', 'if-none-match', 'if-modified-since'];
// content-length / content-encoding 은 넘기지 않는다: fetch 가 gzip 응답을 자동으로 풀기 때문에
// 원래(압축된) 길이를 그대로 주면 브라우저가 본문을 중간에서 잘라 JSON 파싱이 실패한다 → "연결할 수 없어요"
const FORWARD_RESPONSE_HEADERS = ['content-type', 'retry-after', 'cache-control', 'etag', 'last-modified'];
// 분석은 서버 백그라운드 작업으로 돌고 API 요청은 모두 짧다 (작업 접수·진행 조회·캐시 조회)
const PROXY_TIMEOUT_MS = 60_000;

function target(): string {
  return (process.env.API_PROXY_TARGET || 'http://localhost:8000').replace(/\/+$/, '');
}

function clientIp(req: Request): string | null {
  // Next(standalone)는 수신 요청에 x-forwarded-for 를 채워 준다. 앞단 프록시(Cloudflare 등)가 있으면 그 값이 앞에 온다.
  return req.headers.get('x-forwarded-for') ?? req.headers.get('x-real-ip');
}

export async function proxyToApi(req: Request, path: string): Promise<Response> {
  const incoming = new URL(req.url);
  const headers = new Headers();
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }
  const ip = clientIp(req);
  if (ip) headers.set('x-forwarded-for', ip);

  const hasBody = req.method !== 'GET' && req.method !== 'HEAD';
  try {
    const res = await fetch(`${target()}${path}${incoming.search}`, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      cache: 'no-store',
      redirect: 'manual',
      signal: AbortSignal.timeout(PROXY_TIMEOUT_MS),
    });
    const outHeaders = new Headers();
    for (const name of FORWARD_RESPONSE_HEADERS) {
      const value = res.headers.get(name);
      if (value) outHeaders.set(name, value);
    }
    return new Response(res.body, { status: res.status, headers: outHeaders });
  } catch (err) {
    const timeout = err instanceof DOMException && err.name === 'TimeoutError';
    console.error('[Linktem] API proxy error', path, err);
    return Response.json(
      { detail: timeout ? '분석 서버 응답이 너무 오래 걸려요.' : '분석 서버에 연결할 수 없어요.' },
      { status: timeout ? 504 : 502 },
    );
  }
}
