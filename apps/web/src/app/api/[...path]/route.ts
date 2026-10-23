import { proxyToApi } from '@/lib/server/api-proxy';

export const dynamic = 'force-dynamic';
// Vercel 등 서버리스에서 실행될 때의 최대 실행 시간 (플랜 한도 내에서 적용)
export const maxDuration = 60;

type Context = { params: { path: string[] } };

function handler(req: Request, { params }: Context) {
  return proxyToApi(req, `/api/${params.path.map(encodeURIComponent).join('/')}`);
}

export { handler as GET, handler as POST };
