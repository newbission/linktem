import { ListChecks, Share2, ShoppingBasket } from 'lucide-react';

const STEPS = [
  { icon: Share2, title: '공유하기', desc: '유튜브·인스타·틱톡에서 [공유] → Linktem 선택 (또는 링크 복사)' },
  { icon: ShoppingBasket, title: 'AI 분석', desc: '영상 속 상품을 찾아 스틸컷·판매처·최저가를 붙여드려요' },
  { icon: ListChecks, title: '체크하며 장보기', desc: '오프라인 저장하면 인터넷 없이도 체크할 수 있어요' },
];

export function EmptyState() {
  return (
    <section className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-100">
      <h2 className="text-base font-extrabold text-slate-900">이렇게 써보세요</h2>
      <ol className="mt-4 space-y-4">
        {STEPS.map(({ icon: Icon, title, desc }, i) => (
          <li key={title} className="flex gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
              <Icon size={19} aria-hidden />
            </span>
            <div>
              <p className="text-sm font-bold text-slate-900">
                {i + 1}. {title}
              </p>
              <p className="mt-0.5 text-[13px] leading-relaxed text-slate-500">{desc}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-5 rounded-2xl bg-slate-50 p-3 text-xs leading-relaxed text-slate-500">
        💡 홈 화면에 앱을 설치하면 SNS 앱의 [공유하기] 목록에 Linktem 이 나타나요.
      </p>
    </section>
  );
}
