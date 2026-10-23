import { proxyToApi } from '@/lib/server/api-proxy';

export const dynamic = 'force-dynamic';

export function GET(req: Request) {
  return proxyToApi(req, '/health');
}
