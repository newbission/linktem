import { Suspense } from 'react';

import { HomeClient } from '@/components/HomeClient';

export default function HomePage() {
  // useSearchParams(?url=) 를 쓰는 클라이언트 컴포넌트는 Suspense 경계가 필요
  return (
    <Suspense>
      <HomeClient />
    </Suspense>
  );
}
