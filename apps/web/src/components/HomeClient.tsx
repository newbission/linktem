'use client';

import { AlertCircle, CircleCheck, WifiOff, X } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { FeedbackType, RelatedVideo } from '@linktem/types';

import { ApiError, analyzeVideo, fetchRelated, sendFeedback, waitForServer } from '@/lib/api';
import { toEntries, type FilterTab } from '@/lib/grouping';
import { canonicalVideoKey } from '@/lib/share';
import { useOfflineImages, useOnlineStatus, useShoppingList } from '@/lib/use-shopping-list';

import { AdSlot } from './AdSlot';
import { AnalysisLoading, type AnalysisPhase } from './AnalysisLoading';
import { EmptyState } from './EmptyState';
import { ExportListPanel } from './ExportListPanel';
import { FilterTabs } from './FilterTabs';
import { Footer } from './Footer';
import { Header } from './Header';
import { ListSummary } from './ListSummary';
import { OfflineSaveButton } from './OfflineSaveButton';
import { ShoppingList } from './ShoppingList';
import { UrlInputForm } from './UrlInputForm';

// 앱을 열 때 백그라운드 앙상블 개선분을 받아올 미확정 영상 수 (서버 레이트 리밋 고려)
const MAX_SILENT_REFRESH = 3;
const MAX_RELATED_PREFETCH = 10;

export function HomeClient() {
  const params = useSearchParams();
  const router = useRouter();
  const online = useOnlineStatus();
  const {
    list,
    hydrated,
    stats,
    offlineSavedAt,
    offlineStale,
    markOfflineSaved,
    addVideo,
    refreshVideo,
    removeVideo,
    toggleChecked,
    resetChecks,
    clearAll,
    setFeedback,
    hideItem,
  } = useShoppingList();

  const [tab, setTab] = useState<FilterTab>('all');
  const [pendingUrl, setPendingUrl] = useState<string | null>(null);
  const [phase, setPhase] = useState<AnalysisPhase>('analyzing');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [related, setRelated] = useState<Record<string, RelatedVideo[]>>({});
  const abortRef = useRef<AbortController | null>(null);
  const listTopRef = useRef<HTMLDivElement>(null);

  const entries = useMemo(() => toEntries(list.videos, list.checked), [list.videos, list.checked]);
  const imageUrls = useMemo(() => entries.map((e) => e.item.image_url).filter(Boolean), [entries]);
  const imageMap = useOfflineImages(imageUrls, offlineSavedAt);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 3500);
    return () => clearTimeout(timer);
  }, [notice]);

  const loadRelated = useCallback(async (videoId: string) => {
    try {
      const res = await fetchRelated(videoId);
      setRelated((prev) => ({ ...prev, ...res.items }));
    } catch {
      /* 관련 영상은 부가 정보 — 실패해도 무시 */
    }
  }, []);

  /** 분석 성공 시 true (입력창은 성공했을 때만 비움) */
  const analyze = useCallback(
    async (url: string): Promise<boolean> => {
      if (!navigator.onLine) {
        setError('오프라인 상태에서는 새 영상을 분석할 수 없어요.');
        return false;
      }
      if (abortRef.current) return false; // 분석 중 중복 요청 차단

      // 이미 내 리스트에 있는 영상이면 서버 호출 없이 바로 보여주고, 미확정이면 뒤에서 조용히 갱신
      const key = canonicalVideoKey(url);
      const existing = key ? list.videos.find((v) => canonicalVideoKey(v.source_url) === key) : undefined;
      if (existing) {
        addVideo(existing);
        setError(null);
        setNotice('이미 리스트에 있는 영상이에요');
        requestAnimationFrame(() => listTopRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
        if (!existing.is_locked && existing.source_url) {
          analyzeVideo(existing.source_url).then(refreshVideo, () => undefined);
        }
        return true;
      }

      const controller = new AbortController();
      abortRef.current = controller;
      setError(null);
      setNotice(null);
      setPhase('analyzing');
      setPendingUrl(url);
      const { signal } = controller;
      try {
        // 슬립 중인 무료 서버면 깨어날 때까지 '서버 깨우는 중' 단계로 대기
        await waitForServer({ signal, onWaking: () => setPhase('connecting') });
        setPhase('analyzing');
        let result;
        try {
          result = await analyzeVideo(url, signal);
        } catch (err) {
          // 분석 도중 연결이 끊기면(서버 재시작 등) 한 번만 서버를 기다렸다가 재시도
          if (!(err instanceof ApiError && err.status === 0)) throw err;
          await waitForServer({ signal, onWaking: () => setPhase('connecting') });
          setPhase('analyzing');
          result = await analyzeVideo(url, signal);
        }
        addVideo(result);
        setNotice(`${result.items.length}개 상품을 리스트에 담았어요`);
        void loadRelated(result.video_id);
        requestAnimationFrame(() => listTopRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
        return true;
      } catch (err) {
        if (err instanceof ApiError && err.status === 499) return false;
        setError(err instanceof Error ? err.message : '분석에 실패했어요.');
        return false;
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
          setPendingUrl(null);
        }
      }
    },
    [addVideo, refreshVideo, loadRelated, list.videos],
  );

  // 분석 중 리스트는 키보드 포커스까지 차단 (pointer-events 만으로는 Tab 이동이 가능)
  useEffect(() => {
    if (listTopRef.current) listTopRef.current.inert = pendingUrl !== null;
  }, [pendingUrl]);

  const cancelAnalysis = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setPendingUrl(null);
  }, []);

  // Web Share Target(/share → /?url=) 또는 외부 링크로 들어온 URL 자동 분석
  const handledParamRef = useRef(false);
  useEffect(() => {
    if (!hydrated || handledParamRef.current) return;
    const sharedUrl = params.get('url');
    const shareError = params.get('share_error');
    if (!sharedUrl && !shareError) return;
    handledParamRef.current = true;
    router.replace('/', { scroll: false });
    if (sharedUrl) void analyze(sharedUrl);
    else setError('공유된 내용에서 영상 링크를 찾지 못했어요. 링크를 직접 붙여넣어 주세요.');
  }, [hydrated, params, router, analyze]);

  // 앱을 열면: 관련 영상 로드 + 아직 동결되지 않은 영상의 개선된 결과를 조용히 갱신
  const refreshedRef = useRef(false);
  useEffect(() => {
    if (!hydrated || refreshedRef.current || !navigator.onLine) return;
    refreshedRef.current = true;
    const videos = list.videos;
    videos.slice(0, MAX_RELATED_PREFETCH).forEach((v) => void loadRelated(v.video_id));
    const targets = videos.filter((v) => !v.is_locked && v.source_url).slice(0, MAX_SILENT_REFRESH);
    (async () => {
      for (const video of targets) {
        try {
          // 같은 사용자의 재요청은 서버에서 회차를 올리지 않으므로 캐시 조회와 같음
          refreshVideo(await analyzeVideo(video.source_url!));
        } catch {
          /* 조용한 갱신 실패는 무시 */
        }
      }
    })();
  }, [hydrated, list.videos, loadRelated, refreshVideo]);

  const handleFeedback = useCallback(
    async (itemId: string, type: FeedbackType | null) => {
      const previous = list.feedback[itemId] ?? null;
      setFeedback(itemId, type);
      try {
        // '되돌리기'는 "영상 속 제품이 맞아요(SAME)" 로 재투표 → 서버는 1인 1표로 갱신
        const res = await sendFeedback({ item_id: itemId, feedback_type: type ?? 'SAME' });
        if (res.is_hidden) {
          hideItem(itemId);
          setNotice('여러 분이 다른 제품이라고 알려주셔서 리스트에서 뺐어요.');
        }
      } catch (err) {
        setFeedback(itemId, previous);
        setError(err instanceof Error ? err.message : '피드백을 보내지 못했어요.');
      }
    },
    [list.feedback, setFeedback, hideItem],
  );

  const hasItems = list.videos.length > 0;

  return (
    <>
      <Header online={online} />

      <main className="mx-auto max-w-xl space-y-5 px-4 pb-8 pt-5">
        <section className="space-y-3">
          <div>
            <h1 className="text-[22px] font-extrabold leading-tight tracking-tight text-slate-900">
              링크 하나로 완성되는
              <br />
              <span className="text-brand-600">스마트 장보기 리스트</span>
            </h1>
            <p className="mt-1.5 text-sm text-slate-500">SNS 장보기·살림템 영상 속 상품을 AI가 체크리스트로 만들어요.</p>
          </div>
          <UrlInputForm loading={pendingUrl !== null} disabled={!online} onSubmit={analyze} />
        </section>

        {!online && (
          <div className="flex items-start gap-2 rounded-2xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200">
            <WifiOff size={17} className="mt-0.5 shrink-0" aria-hidden />
            <p>
              오프라인 모드예요. {offlineSavedAt ? '저장해 둔 리스트로 장을 볼 수 있어요.' : '저장된 리스트만 볼 수 있어요.'}
              <br />
              체크한 내용은 이 기기에 저장돼요.
            </p>
          </div>
        )}

        {error && (
          <div role="alert" className="flex items-start gap-2 rounded-2xl bg-red-50 p-3 text-sm text-red-800 ring-1 ring-red-200">
            <AlertCircle size={17} className="mt-0.5 shrink-0" aria-hidden />
            <p className="flex-1">{error}</p>
            <button type="button" onClick={() => setError(null)} aria-label="닫기" className="text-red-400">
              <X size={16} />
            </button>
          </div>
        )}

        {pendingUrl && <AnalysisLoading url={pendingUrl} phase={phase} onCancel={cancelAnalysis} />}

        {hydrated && !hasItems && !pendingUrl && <EmptyState />}

        {hasItems && (
          <div
            ref={listTopRef}
            aria-busy={pendingUrl !== null}
            className={`scroll-mt-20 space-y-4 transition-opacity ${
              // 분석 중에는 리스트 조작 잠금 (체크/피드백/관련 영상/내보내기)
              pendingUrl ? 'pointer-events-none select-none opacity-40' : ''
            }`}
          >
            <ListSummary
              done={stats.done}
              total={stats.total}
              videoCount={list.videos.length}
              onResetChecks={resetChecks}
              onClearAll={clearAll}
            />
            <OfflineSaveButton
              list={list}
              savedAt={offlineSavedAt}
              stale={offlineStale}
              online={online}
              onSaved={markOfflineSaved}
            />
            <ExportListPanel list={list} onNotice={setNotice} />
            <FilterTabs value={tab} onChange={setTab} />
            <ShoppingList
              entries={entries}
              tab={tab}
              imageMap={imageMap}
              related={related}
              feedback={list.feedback}
              online={online}
              onToggle={toggleChecked}
              onFeedback={handleFeedback}
              onOpenRelated={analyze}
              onRemoveVideo={removeVideo}
            />
          </div>
        )}

        <AdSlot size="banner" slot="home-bottom" />
      </main>

      <Footer />

      {notice && (
        <div
          role="status"
          className="fixed inset-x-0 bottom-6 z-40 mx-auto flex w-fit max-w-[90vw] items-center gap-2 rounded-full bg-slate-900 px-4 py-2.5 text-sm font-medium text-white shadow-lg"
        >
          <CircleCheck size={16} className="text-brand-400" aria-hidden />
          {notice}
        </div>
      )}
    </>
  );
}
