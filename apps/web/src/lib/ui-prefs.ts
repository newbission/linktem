'use client';

import { useCallback, useEffect, useState } from 'react';

/** 보기 설정 — 기기별 취향이라 리스트(계정 동기화 대상)와 분리해 이 기기에만 저장 */
interface UiPrefs {
  /** 간단히 보기: 한 줄에 번호·이름만 */
  compact: boolean;
  /** 접어 둔 묶음 키 (판매처별: 'retailer:이마트', 영상별: 'video:<id>') */
  collapsed: string[];
}

const STORAGE_KEY = 'linktem:ui:v1';
const DEFAULT_PREFS: UiPrefs = { compact: false, collapsed: [] };
// 접힘 기록이 끝없이 쌓이지 않도록 (지운 영상의 키 등)
const MAX_COLLAPSED = 200;

function load(): UiPrefs {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_PREFS;
    const parsed = JSON.parse(raw) as Partial<UiPrefs>;
    return {
      compact: Boolean(parsed.compact),
      collapsed: Array.isArray(parsed.collapsed) ? parsed.collapsed.filter((k) => typeof k === 'string') : [],
    };
  } catch {
    return DEFAULT_PREFS;
  }
}

export function groupKey(tab: 'retailer' | 'video', key: string): string {
  return `${tab}:${key}`;
}

export function useUiPrefs() {
  const [prefs, setPrefs] = useState<UiPrefs>(DEFAULT_PREFS);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setPrefs(load());
    setLoaded(true);
  }, []);

  useEffect(() => {
    if (!loaded) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    } catch {
      /* 저장 실패는 무시 (사생활 보호 모드 등) */
    }
  }, [prefs, loaded]);

  const setCompact = useCallback((compact: boolean) => setPrefs((p) => ({ ...p, compact })), []);

  const toggleCollapsed = useCallback(
    (key: string) =>
      setPrefs((p) => {
        const collapsed = p.collapsed.includes(key)
          ? p.collapsed.filter((k) => k !== key)
          : [...p.collapsed, key].slice(-MAX_COLLAPSED);
        return { ...p, collapsed };
      }),
    [],
  );

  /** 여러 묶음을 한 번에 접거나 펼치기 */
  const setCollapsedMany = useCallback(
    (keys: string[], collapsed: boolean) =>
      setPrefs((p) => {
        const rest = p.collapsed.filter((k) => !keys.includes(k));
        return { ...p, collapsed: collapsed ? [...rest, ...keys].slice(-MAX_COLLAPSED) : rest };
      }),
    [],
  );

  return {
    compact: prefs.compact,
    collapsed: prefs.collapsed,
    setCompact,
    toggleCollapsed,
    setCollapsedMany,
  };
}
