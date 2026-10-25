'use client';

import { AlertCircle, CircleCheck, WifiOff, X } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { AnalysisJob, RelatedVideo, VideoAnalysisResponse } from '@linktem/types';

import { ApiError, analyzeVideo, fetchRelated, lookupVideos, sendFeedback, unlinkRelated, waitForServer } from '@/lib/api';
import { groupEntries, toEntries, type FilterTab } from '@/lib/grouping';
import { itemNumbers } from '@/lib/numbering';
import { visibleRelated } from '@/lib/related';
import { toggleReport, type SendReports } from '@/lib/reports';
import { groupKey, useUiPrefs } from '@/lib/ui-prefs';
import { canonicalVideoKey } from '@/lib/share';
import { isActiveJob, useJobPolling } from '@/lib/use-job-polling';
import { useOfflineImages, useOnlineStatus, useShoppingList } from '@/lib/use-shopping-list';

import { AdSlot } from './AdSlot';
import { EmptyState } from './EmptyState';
import { ExportListPanel } from './ExportListPanel';
import { FilterTabs } from './FilterTabs';
import { Footer } from './Footer';
import { Header } from './Header';
import { ImageViewer } from './ImageViewer';
import { ListSummary } from './ListSummary';
import { ListViewControls } from './ListViewControls';
import { MyVideos } from './MyVideos';
import { OfflineSaveButton } from './OfflineSaveButton';
import { ShoppingList, videoGroupId } from './ShoppingList';
import { UrlInputForm } from './UrlInputForm';

// 앱을 열 때 백그라운드 앙상블 개선분을 받아올 미확정 영상 수 (GET /api/videos 한 번에 조회, 서버 상한 30)
const MAX_SILENT_REFRESH = 30;
const MAX_RELATED_PREFETCH = 10;

function scrollToTop(el: HTMLElement | null) {
  requestAnimationFrame(() => el?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
}

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
    upsertJob,
    completeJob,
    removeJob,
    toggleChecked,
    resetChecks,
    clearAll,
    setReports,
    clearItemImage,
    hideItem,
    setRelatedUnlinked,
  } = useShoppingList();

  const [tab, setTab] = useState<FilterTab>('all');
  // 링크 접수 중 (서버 깨우기 + 작업 접수까지만) — 분석 자체는 서버 백그라운드 작업
  const [submitting, setSubmitting] = useState<'connecting' | 'sending' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [related, setRelated] = useState<Record<string, RelatedVideo[]>>({});
  // 확대 보기 중인 항목의 item.id (목록 순서가 바뀌어도 같은 상품을 유지)
  const [viewerItemId, setViewerItemId] = useState<string | null>(null);
  const submittingRef = useRef(false);
  const listTopRef = useRef<HTMLDivElement>(null);
  const myVideosRef = useRef<HTMLDivElement>(null);

  const entries = useMemo(() => toEntries(list.videos, list.checked), [list.videos, list.checked]);
  const numbers = useMemo(() => itemNumbers(list.videos), [list.videos]);
  // 내가 뗀 연결은 서버 응답과 상관없이 이 기기에서 계속 숨긴다 (접속 IP 가 바뀌어도)
  const shownRelated = useMemo(() => visibleRelated(related, list.unlinked), [related, list.unlinked]);
  const { compact, collapsed, setCompact, toggleCollapsed, setCollapsedMany } = useUiPrefs();
  const groupKeys = useMemo(
    () => (tab === 'all' ? [] : groupEntries(entries, tab).map((g) => groupKey(tab, g.key))),
    [entries, tab],
  );
  const allCollapsed = groupKeys.length > 0 && groupKeys.every((k) => collapsed.includes(k));
  const imageUrls = useMemo(() => entries.map((e) => e.item.image_url).filter(Boolean), [entries]);
  const imageMap = useOfflineImages(imageUrls, offlineSavedAt);
  // 확대 보기 넘기기 순서 = 지금 탭에서 보이는 순서 (이미지가 있는 항목만)
  const viewerEntries = useMemo(
    () => groupEntries(entries, tab).flatMap((g) => g.entries).filter((e) => e.item.image_url || e.item.thumb_url),
    [entries, tab],
  );
  const viewerIndex = viewerItemId ? viewerEntries.findIndex((e) => e.item.id === viewerItemId) : -1;

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

  /** 리스트에 있는 영상들의 최신 결과를 조용히 반영 (회차를 올리지 않는 조회, 레이트 리밋 없음) */
  const refreshVideos = useCallback(
    async (videos: VideoAnalysisResponse[]) => {
      const ids = videos
        .filter((v) => !v.is_locked)
        .map((v) => v.video_id)
        .slice(0, MAX_SILENT_REFRESH);
      if (ids.length === 0) return;
      try {
        const res = await lookupVideos(ids);
        res.videos.forEach(refreshVideo);
      } catch {
        /* 조용한 갱신 실패는 무시 */
      }
    },
    [refreshVideo],
  );

  /** 링크 접수 성공 시 true (입력창은 성공했을 때만 비움). 분석은 서버 백그라운드 작업으로 진행된다. */
  const analyze = useCallback(
    async (url: string): Promise<boolean> => {
      if (!navigator.onLine) {
        setError('오프라인 상태에서는 새 영상을 분석할 수 없어요.');
        return false;
      }
      // 접수 중 연타만 막는다 (접수가 끝나면 다른 링크를 바로 이어서 넣을 수 있음)
      if (submittingRef.current) return false;

      const key = canonicalVideoKey(url);
      // 이미 내 리스트에 있는 영상이면 서버 호출 없이 바로 보여주고, 미확정이면 뒤에서 조용히 갱신
      const existing = key ? list.videos.find((v) => canonicalVideoKey(v.source_url) === key) : undefined;
      if (existing) {
        addVideo(existing);
        setError(null);
        setNotice('이미 리스트에 있는 영상이에요');
        scrollToTop(listTopRef.current);
        void refreshVideos([existing]);
        return true;
      }
      const running = key
        ? list.jobs.find((j) => isActiveJob(j) && canonicalVideoKey(j.source_url) === key)
        : undefined;
      if (running) {
        setError(null);
        setNotice('이미 분석 중인 영상이에요');
        scrollToTop(myVideosRef.current);
        return true;
      }

      submittingRef.current = true;
      setError(null);
      setNotice(null);
      setSubmitting('sending');
      try {
        // 슬립 중인 무료 서버면 깨어날 때까지 대기
        await waitForServer({ onWaking: () => setSubmitting('connecting') });
        setSubmitting('sending');
        let res;
        try {
          res = await analyzeVideo(url);
        } catch (err) {
          // 접수 도중 연결이 끊기면(서버 재시작 등) 한 번만 서버를 기다렸다가 재시도 — 같은 링크는 서버가 작업 1개로 합친다
          if (!(err instanceof ApiError && err.status === 0)) throw err;
          await waitForServer({ onWaking: () => setSubmitting('connecting') });
          setSubmitting('sending');
          res = await analyzeVideo(url);
        }
        if (res.video) {
          // 다른 사람이 이미 분석한 영상 → 바로 리스트에
          addVideo(res.video);
          setNotice(`${res.video.items.length}개 상품을 리스트에 담았어요`);
          void loadRelated(res.video.video_id);
          scrollToTop(listTopRef.current);
        } else if (res.job) {
          // 같은 링크의 이전 실패 기록은 새 작업으로 대체
          list.jobs
            .filter((j) => !isActiveJob(j) && canonicalVideoKey(j.source_url) === key)
            .forEach((j) => removeJob(j.job_id));
          upsertJob(res.job);
          setNotice('분석을 시작했어요. 다른 일을 하셔도 돼요');
          scrollToTop(myVideosRef.current);
        }
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : '분석을 시작하지 못했어요.');
        return false;
      } finally {
        submittingRef.current = false;
        setSubmitting(null);
      }
    },
    [addVideo, upsertJob, removeJob, loadRelated, refreshVideos, list.videos, list.jobs],
  );

  // 진행 중 작업 조회: 완료되면 리스트에 넣고, 실패하면 사유와 '다시 시도'를 보여준다
  useJobPolling(list.jobs, hydrated && online, {
    onProgress: upsertJob,
    onDone: (job, video) => {
      completeJob(job.job_id, video);
      setNotice(`분석 완료! ${video.items.length}개 상품을 리스트에 담았어요`);
      void loadRelated(video.video_id);
    },
    onFailed: upsertJob,
  });

  const retryJob = useCallback(
    (job: AnalysisJob) => {
      removeJob(job.job_id);
      void analyze(job.source_url);
    },
    [analyze, removeJob],
  );

  const showVideo = useCallback((videoId: string) => {
    setTab('video');
    setCollapsedMany([groupKey('video', videoId)], false);
    // 탭 전환 렌더 후 해당 영상 묶음으로 이동
    setTimeout(() => {
      document.getElementById(videoGroupId(videoId))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  }, [setCollapsedMany]);

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

  // 앱을 열면: 관련 영상 로드 + 아직 동결되지 않은 영상의 개선된 결과를 조용히 갱신 (요청 1번)
  const refreshedRef = useRef(false);
  useEffect(() => {
    if (!hydrated || refreshedRef.current || !navigator.onLine) return;
    refreshedRef.current = true;
    list.videos.slice(0, MAX_RELATED_PREFETCH).forEach((v) => void loadRelated(v.video_id));
    void refreshVideos(list.videos);
  }, [hydrated, list.videos, loadRelated, refreshVideos]);

  /** '보내기'를 누른 제보 묶음을 서버로 보낸다. 성공한 것만 '보낸 제보'로 저장 */
  const handleSendReports = useCallback<SendReports>(
    async (itemId, add, remove, comment) => {
      let current = list.feedback[itemId] ?? [];
      let hidden = false;
      let imageReset = false;
      try {
        for (const type of remove) {
          await sendFeedback({ item_id: itemId, feedback_type: type, cancel: true });
          current = toggleReport(current, type, true);
        }
        for (const type of add) {
          const res = await sendFeedback({ item_id: itemId, feedback_type: type, comment });
          current = toggleReport(current, type, false);
          hidden ||= res.is_hidden;
          imageReset ||= res.image_reset;
        }
      } catch (err) {
        setReports(itemId, current);
        setError(err instanceof Error ? `제보를 다 보내지 못했어요. ${err.message}` : '제보를 보내지 못했어요.');
        return false;
      }
      setReports(itemId, current);
      if (hidden) {
        hideItem(itemId);
        setNotice('여러 분이 알려주셔서 이 제품을 리스트에서 뺐어요.');
      } else if (imageReset) {
        clearItemImage(itemId);
        setNotice('사진을 다시 고르고 있어요. 잠시 후 바뀌어요');
        // 서버가 새 사진을 고르는 데 보통 수십 초 — 두 번에 나눠 조용히 받아온다
        const video = list.videos.find((v) => v.items.some((i) => i.id === itemId));
        if (video) {
          setTimeout(() => void refreshVideos([{ ...video, is_locked: false }]), 30_000);
          setTimeout(() => void refreshVideos([{ ...video, is_locked: false }]), 90_000);
        }
      } else {
        setNotice(add.length > 0 ? '제보를 보냈어요. 고마워요!' : '제보를 취소했어요');
      }
      return true;
    },
    [list.feedback, list.videos, setReports, hideItem, clearItemImage, refreshVideos],
  );

  /** '이 영상의 제품은 달라요' — 바로 숨기고 서버에 알린다 (실패하면 되돌림) */
  const handleUnlinkRelated = useCallback(
    async (itemId: string, target: RelatedVideo) => {
      setRelatedUnlinked(itemId, target.other_item_id, true);
      try {
        const res = await unlinkRelated({ item_id: itemId, other_item_id: target.other_item_id });
        setNotice(
          res.unlinked
            ? '여러 분이 알려주셔서 이 연결을 모두에게서 뗐어요.'
            : '연결을 뗐어요. 알려주셔서 고마워요!',
        );
      } catch (err) {
        setRelatedUnlinked(itemId, target.other_item_id, false);
        setError(err instanceof Error ? `연결을 떼지 못했어요. ${err.message}` : '연결을 떼지 못했어요.');
      }
    },
    [setRelatedUnlinked],
  );

  const hasItems = list.videos.length > 0;
  const hasJobs = list.jobs.length > 0;

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
          <UrlInputForm loading={submitting !== null} disabled={!online} onSubmit={analyze} />
          {submitting === 'connecting' && (
            <p role="status" className="px-1 text-xs text-slate-500">
              서버에 연결하고 있어요. 최대 1분 정도 걸릴 수 있어요.
            </p>
          )}
        </section>

        {!online && (
          <div className="flex items-start gap-2 rounded-2xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200">
            <WifiOff size={17} className="mt-0.5 shrink-0" aria-hidden />
            <p>
              오프라인 모드예요. {offlineSavedAt ? '저장해 둔 리스트로 장을 볼 수 있어요.' : '저장된 리스트만 볼 수 있어요.'}
              <br />
              체크한 내용은 이 기기에 저장돼요.
              {list.jobs.some(isActiveJob) && ' 분석 중인 영상은 다시 연결되면 결과를 받아와요.'}
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

        <div ref={myVideosRef} className="scroll-mt-20">
          <MyVideos
            jobs={list.jobs}
            videos={list.videos}
            addedAt={list.addedAt}
            checked={list.checked}
            online={online}
            onRetry={retryJob}
            onDismissJob={removeJob}
            onShowVideo={showVideo}
            onRemoveVideo={removeVideo}
          />
        </div>

        {hydrated && !hasItems && !hasJobs && <EmptyState />}

        {hasItems && (
          <div ref={listTopRef} className="scroll-mt-20 space-y-4">
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
            <ListViewControls
              compact={compact}
              onCompactChange={setCompact}
              groupCount={groupKeys.length}
              allCollapsed={allCollapsed}
              onCollapseAll={(value) => setCollapsedMany(groupKeys, value)}
            />
            <ShoppingList
              entries={entries}
              tab={tab}
              imageMap={imageMap}
              related={shownRelated}
              feedback={list.feedback}
              numbers={numbers}
              online={online}
              compact={compact}
              collapsed={collapsed}
              onToggleCollapsed={toggleCollapsed}
              onToggle={toggleChecked}
              onSendReports={handleSendReports}
              onOpenRelated={analyze}
              onUnlinkRelated={handleUnlinkRelated}
              onOpenImage={setViewerItemId}
              onRemoveVideo={removeVideo}
            />
          </div>
        )}

        <AdSlot size="banner" slot="home-bottom" />
      </main>

      <Footer />

      {viewerIndex >= 0 && (
        <ImageViewer
          entries={viewerEntries}
          index={viewerIndex}
          imageMap={imageMap}
          numbers={numbers}
          online={online}
          onIndexChange={(i) => setViewerItemId(viewerEntries[i]?.item.id ?? null)}
          onClose={() => setViewerItemId(null)}
        />
      )}

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
