'use client';

import { CircleCheck, CloudDownload, LoaderCircle } from 'lucide-react';
import { useState } from 'react';

import { formatRelativeTime } from '@/lib/format';
import type { StoredList } from '@/lib/list-store';
import { saveOffline } from '@/lib/offline-db';

interface Props {
  list: StoredList;
  savedAt: number | null;
  /** 저장 이후 영상/이미지 구성이 바뀌었는지 */
  stale: boolean;
  online: boolean;
  onSaved: (savedAt: number, savedList: StoredList) => void;
}

export function OfflineSaveButton({ list, savedAt, stale: staleProp, online, onSaved }: Props) {
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const saving = progress !== null;
  const stale = staleProp && !saving;

  const save = async () => {
    setMessage(null);
    setProgress({ done: 0, total: 0 });
    try {
      const result = await saveOffline(list, (done, total) => setProgress({ done, total }));
      onSaved(result.savedAt, list);
      setMessage(
        result.failed > 0
          ? `저장 완료 (이미지 ${result.failed}개는 저장하지 못했어요)`
          : `체크리스트와 이미지 ${result.saved}개를 저장했어요`,
      );
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '오프라인 저장에 실패했어요.');
    } finally {
      setProgress(null);
    }
  };

  return (
    <div className="space-y-1.5">
      <button
        type="button"
        onClick={save}
        disabled={saving || !online || list.videos.length === 0}
        className={`flex w-full items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-bold transition active:scale-[0.99] disabled:opacity-60 ${
          savedAt && !stale ? 'bg-brand-50 text-brand-800 ring-1 ring-brand-200' : 'bg-slate-900 text-white shadow-sm'
        }`}
      >
        {saving ? (
          <>
            <LoaderCircle size={17} className="animate-spin" aria-hidden />
            이미지 저장 중 {progress.total ? `${progress.done}/${progress.total}` : ''}
          </>
        ) : savedAt && !stale ? (
          <>
            <CircleCheck size={17} aria-hidden />
            오프라인 저장됨 · {formatRelativeTime(savedAt)}
          </>
        ) : (
          <>
            <CloudDownload size={17} aria-hidden />
            {stale ? '변경 사항 오프라인에 다시 저장' : '오프라인 장보기 저장'}
          </>
        )}
      </button>
      <p className="px-1 text-center text-[11px] text-slate-500" aria-live="polite">
        {message ?? '마트 지하처럼 인터넷이 안 될 때도 리스트와 사진을 볼 수 있어요.'}
      </p>
    </div>
  );
}
