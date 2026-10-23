import { Coffee } from 'lucide-react';

export function Footer() {
  const donationUrl = process.env.NEXT_PUBLIC_DONATION_URL;
  return (
    <footer className="mt-12 border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-xl space-y-4 px-4 py-8 text-xs leading-relaxed text-slate-500">
        <p>
          상품 정보는 AI가 영상을 분석해 자동으로 만든 것으로 실제와 다를 수 있어요. 가격·재고는 판매처에서 꼭
          확인해 주세요. 잘못된 상품은 &lsquo;다른 제품이에요&rsquo;로 알려주시면 더 정확해져요.
        </p>
        {donationUrl && (
          <a
            href={donationUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-3.5 py-2 font-bold text-amber-900 transition active:scale-95"
          >
            <Coffee size={14} aria-hidden />
            개발자에게 커피 한 잔 후원하기
          </a>
        )}
        <p className="text-slate-400">© {new Date().getFullYear()} Linktem · 링크 하나로 완성되는 스마트 장보기 리스트</p>
      </div>
    </footer>
  );
}
