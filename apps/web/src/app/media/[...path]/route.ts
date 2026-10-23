import { proxyToApi } from '@/lib/server/api-proxy';

export const dynamic = 'force-dynamic';

type Context = { params: { path: string[] } };

/** 로컬 저장소(STORAGE_BACKEND=local) 스틸컷: /media/* → API /media/* */
export function GET(req: Request, { params }: Context) {
  return proxyToApi(req, `/media/${params.path.map(encodeURIComponent).join('/')}`);
}
