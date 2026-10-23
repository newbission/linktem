'use client';

import { openDB, type DBSchema, type IDBPDatabase } from 'idb';

import type { StoredList } from './list-store';

/**
 * 오프라인 장보기 저장소 (IndexedDB)
 * - images:    스틸컷 WebP Blob (key: 원본 image_url)
 * - snapshots: 체크리스트 텍스트 스냅샷 (key: 'current')
 */
interface LinktemDB extends DBSchema {
  images: {
    key: string;
    value: { url: string; blob: Blob; savedAt: number };
  };
  snapshots: {
    key: string;
    value: { id: string; list: StoredList; savedAt: number };
  };
}

const DB_NAME = 'linktem';
const DB_VERSION = 1;
const SNAPSHOT_ID = 'current';
const FETCH_CONCURRENCY = 4;

let dbPromise: Promise<IDBPDatabase<LinktemDB>> | null = null;

function getDB(): Promise<IDBPDatabase<LinktemDB>> {
  if (typeof indexedDB === 'undefined') {
    return Promise.reject(new Error('이 브라우저는 오프라인 저장을 지원하지 않아요.'));
  }
  dbPromise ??= openDB<LinktemDB>(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains('images')) db.createObjectStore('images', { keyPath: 'url' });
      if (!db.objectStoreNames.contains('snapshots')) db.createObjectStore('snapshots', { keyPath: 'id' });
    },
  });
  return dbPromise;
}

export interface OfflineSaveResult {
  total: number;
  saved: number;
  failed: number;
  savedAt: number;
}

export function collectImageUrls(list: StoredList): string[] {
  const urls = list.videos.flatMap((v) => v.items.map((i) => i.image_url)).filter(Boolean);
  return Array.from(new Set(urls));
}

/** 체크리스트 텍스트 + 모든 스틸컷 Blob 을 IndexedDB 에 영구 저장 */
export async function saveOffline(
  list: StoredList,
  onProgress?: (done: number, total: number) => void,
): Promise<OfflineSaveResult> {
  const db = await getDB();
  const urls = collectImageUrls(list);
  const existing = new Set(await db.getAllKeys('images'));
  let done = 0;
  let saved = 0;
  let failed = 0;

  const queue = [...urls];
  const worker = async () => {
    while (queue.length) {
      const url = queue.shift()!;
      try {
        if (!existing.has(url)) {
          const res = await fetch(url, { mode: 'cors', cache: 'force-cache' });
          if (!res.ok) throw new Error(String(res.status));
          const blob = await res.blob();
          await db.put('images', { url, blob, savedAt: Date.now() });
        }
        saved += 1;
      } catch {
        failed += 1;
      } finally {
        done += 1;
        onProgress?.(done, urls.length);
      }
    }
  };
  await Promise.all(Array.from({ length: Math.min(FETCH_CONCURRENCY, urls.length) }, worker));

  // 리스트에서 빠진 이미지 정리
  const keep = new Set(urls);
  const tx = db.transaction('images', 'readwrite');
  for (const key of await tx.store.getAllKeys()) {
    if (!keep.has(key)) await tx.store.delete(key);
  }
  await tx.done;

  const savedAt = Date.now();
  await db.put('snapshots', { id: SNAPSHOT_ID, list, savedAt });

  // 브라우저가 저장 공간을 임의로 비우지 않도록 영구 저장 요청
  try {
    await navigator.storage?.persist?.();
  } catch {
    /* 미지원 브라우저 */
  }
  return { total: urls.length, saved, failed, savedAt };
}

/** 오프라인 저장본과 현재 리스트의 이미지 구성이 같은지 비교하기 위한 시그니처 */
export function offlineSignature(list: StoredList): string {
  return collectImageUrls(list).sort().join('|');
}

/** 체크/피드백 상태만 스냅샷에 반영 (영상·이미지 구성은 '오프라인 저장'을 눌렀을 때만 바뀜) */
export async function updateSnapshotChecks(list: StoredList): Promise<void> {
  const db = await getDB();
  const current = await db.get('snapshots', SNAPSHOT_ID);
  if (!current) return;
  await db.put('snapshots', {
    ...current,
    list: { ...current.list, checked: list.checked, feedback: list.feedback },
  });
}

export async function loadSnapshot(): Promise<{ list: StoredList; savedAt: number } | null> {
  try {
    const db = await getDB();
    const snap = await db.get('snapshots', SNAPSHOT_ID);
    return snap ? { list: snap.list, savedAt: snap.savedAt } : null;
  } catch {
    return null;
  }
}

/** 저장된 Blob 들을 object URL 로 변환 (호출 측에서 revokeObjectURL 책임) */
export async function loadImageObjectUrls(urls: string[]): Promise<Record<string, string>> {
  try {
    const db = await getDB();
    const result: Record<string, string> = {};
    await Promise.all(
      urls.map(async (url) => {
        const record = await db.get('images', url);
        if (record) result[url] = URL.createObjectURL(record.blob);
      }),
    );
    return result;
  } catch {
    return {};
  }
}

export async function clearOffline(): Promise<void> {
  const db = await getDB();
  await Promise.all([db.clear('images'), db.clear('snapshots')]);
}
