'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { FeedbackType, VideoAnalysisResponse } from '@linktem/types';

import { EMPTY_LIST, loadList, saveList, type StoredList } from './list-store';
import { loadImageObjectUrls, loadSnapshot, offlineSignature, updateSnapshotChecks } from './offline-db';

/** 장보기 리스트 상태 (localStorage 영속) + 오프라인 스냅샷 동기화 */
export function useShoppingList() {
  const [list, setList] = useState<StoredList>(EMPTY_LIST);
  const [hydrated, setHydrated] = useState(false);
  const [offlineSavedAt, setOfflineSavedAt] = useState<number | null>(null);
  const [savedSignature, setSavedSignature] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const local = loadList();
      const snapshot = await loadSnapshot();
      if (cancelled) return;
      if (local && local.videos.length > 0) {
        setList(local);
      } else if (snapshot) {
        // localStorage 가 비워졌어도 오프라인 저장본이 있으면 복구
        setList(snapshot.list);
      }
      setOfflineSavedAt(snapshot?.savedAt ?? null);
      setSavedSignature(snapshot ? offlineSignature(snapshot.list) : null);
      setHydrated(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveList(list);
    if (offlineSavedAt) void updateSnapshotChecks(list).catch(() => undefined);
  }, [list, hydrated, offlineSavedAt]);

  const markOfflineSaved = useCallback((savedAt: number, savedList: StoredList) => {
    setOfflineSavedAt(savedAt);
    setSavedSignature(offlineSignature(savedList));
  }, []);

  const offlineStale = useMemo(
    () => savedSignature !== null && savedSignature !== offlineSignature(list),
    [savedSignature, list],
  );

  const mutate = useCallback((fn: (prev: StoredList) => StoredList) => {
    setList((prev) => ({ ...fn(prev), updatedAt: Date.now() }));
  }, []);

  /** 새 분석 결과를 맨 앞에 추가 (이미 있는 영상이면 최신 결과로 교체 후 맨 앞으로) */
  const addVideo = useCallback(
    (video: VideoAnalysisResponse) =>
      mutate((prev) => ({ ...prev, videos: [video, ...prev.videos.filter((v) => v.video_id !== video.video_id)] })),
    [mutate],
  );

  /** 위치를 유지한 채 영상 결과만 갱신 (백그라운드 앙상블 개선분 반영) */
  const refreshVideo = useCallback(
    (video: VideoAnalysisResponse) =>
      mutate((prev) => ({
        ...prev,
        videos: prev.videos.map((v) => (v.video_id === video.video_id ? video : v)),
      })),
    [mutate],
  );

  const removeVideo = useCallback(
    (videoId: string) =>
      mutate((prev) => {
        const target = prev.videos.find((v) => v.video_id === videoId);
        const checked = { ...prev.checked };
        target?.items.forEach((i) => delete checked[i.id]);
        return { ...prev, checked, videos: prev.videos.filter((v) => v.video_id !== videoId) };
      }),
    [mutate],
  );

  const toggleChecked = useCallback(
    (itemId: string) =>
      mutate((prev) => {
        const checked = { ...prev.checked };
        if (checked[itemId]) delete checked[itemId];
        else checked[itemId] = true;
        return { ...prev, checked };
      }),
    [mutate],
  );

  const resetChecks = useCallback(() => mutate((prev) => ({ ...prev, checked: {} })), [mutate]);

  const clearAll = useCallback(() => mutate(() => ({ ...EMPTY_LIST })), [mutate]);

  const setFeedback = useCallback(
    (itemId: string, type: FeedbackType | null) =>
      mutate((prev) => {
        const feedback = { ...prev.feedback };
        if (type) feedback[itemId] = type;
        else delete feedback[itemId];
        return { ...prev, feedback };
      }),
    [mutate],
  );

  /** 피드백 임계치로 서버에서 숨겨진 아이템을 로컬에서도 제거 */
  const hideItem = useCallback(
    (itemId: string) =>
      mutate((prev) => ({
        ...prev,
        videos: prev.videos.map((v) => ({ ...v, items: v.items.filter((i) => i.id !== itemId) })),
      })),
    [mutate],
  );

  const stats = useMemo(() => {
    const total = list.videos.reduce((sum, v) => sum + v.items.length, 0);
    const done = list.videos.reduce((sum, v) => sum + v.items.filter((i) => list.checked[i.id]).length, 0);
    return { total, done };
  }, [list]);

  return {
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
  };
}

/** 오프라인 저장된 이미지 Blob → object URL 매핑. savedAt 이 바뀌면 다시 읽는다. */
export function useOfflineImages(urls: string[], savedAt: number | null): Record<string, string> {
  const [map, setMap] = useState<Record<string, string>>({});
  const key = urls.join('|');
  const urlsRef = useRef(urls);
  urlsRef.current = urls;

  useEffect(() => {
    if (!savedAt) {
      setMap({});
      return;
    }
    let cancelled = false;
    let created: Record<string, string> = {};
    loadImageObjectUrls(urlsRef.current).then((result) => {
      if (cancelled) {
        Object.values(result).forEach((u) => URL.revokeObjectURL(u));
        return;
      }
      created = result;
      setMap(result);
    });
    return () => {
      cancelled = true;
      Object.values(created).forEach((u) => URL.revokeObjectURL(u));
    };
  }, [key, savedAt]);

  return map;
}

export function useOnlineStatus(): boolean {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    setOnline(navigator.onLine);
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);
  return online;
}
