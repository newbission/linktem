'use client';

import {
  AlertCircle,
  ChevronDown,
  CircleCheck,
  Clock,
  Download,
  ExternalLink,
  ImageIcon,
  ListVideo,
  LoaderCircle,
  Lock,
  PackageSearch,
  RotateCw,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import { useEffect, useState } from 'react';

import type { AnalysisJob, AnalysisJobStage, VideoAnalysisResponse } from '@linktem/types';

import { formatRelativeTime, platformLabel } from '@/lib/format';
import { isActiveJob } from '@/lib/use-job-polling';

const STAGES: { stage: AnalysisJobStage; label: string; icon: typeof Download }[] = [
  { stage: 'queued', label: '순서를 기다리는 중', icon: Clock },
  { stage: 'downloading', label: '영상을 가져오는 중', icon: Download },
  { stage: 'analyzing', label: 'AI가 상품을 찾는 중', icon: PackageSearch },
  { stage: 'capturing', label: '스틸컷을 만드는 중', icon: ImageIcon },
  { stage: 'saving', label: '거의 다 됐어요', icon: LoaderCircle },
];

// 입력 오류라 같은 링크로 다시 해도 결과가 같은 실패 (영상 길이 초과, 지원하지 않는 링크)
const NON_RETRYABLE_CODES = new Set([400, 413]);
const COLLAPSED_VIDEO_COUNT = 3;

interface Props {
  jobs: AnalysisJob[];
  videos: VideoAnalysisResponse[];
  addedAt: Record<string, number>;
  checked: Record<string, boolean>;
  online: boolean;
  onRetry: (job: AnalysisJob) => void;
  onDismissJob: (jobId: string) => void;
  onShowVideo: (videoId: string) => void;
  onRemoveVideo: (videoId: string) => void;
}

/** 분석 중·실패한 작업과 리스트에 담긴 영상을 한곳에서 보여주는 '내 분석 영상' */
export function MyVideos({
  jobs,
  videos,
  addedAt,
  checked,
  online,
  onRetry,
  onDismissJob,
  onShowVideo,
  onRemoveVideo,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const activeCount = jobs.filter(isActiveJob).length;
  const total = jobs.length + videos.length;
  if (total === 0) return null;

  const visibleVideos = expanded ? videos : videos.slice(0, COLLAPSED_VIDEO_COUNT);
  const hiddenCount = videos.length - visibleVideos.length;

  return (
    <section aria-labelledby="my-videos-title" className="rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
      <header className="flex items-center justify-between gap-2">
        <h2 id="my-videos-title" className="flex items-center gap-1.5 text-base font-extrabold text-slate-900">
          <ListVideo size={18} className="text-brand-600" aria-hidden />내 분석 영상
          <span className="text-sm font-semibold text-slate-400">{total}</span>
        </h2>
        {activeCount > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-xs font-bold text-brand-700">
            <LoaderCircle size={12} className="animate-spin" aria-hidden />
            {activeCount}개 분석 중
          </span>
        )}
      </header>

      {activeCount > 0 && (
        <p className="mt-1 text-xs text-slate-500">앱을 닫거나 다른 일을 해도 분석은 계속돼요. 끝나면 리스트에 들어와 있어요.</p>
      )}

      <ul className="mt-3 space-y-2">
        {jobs.map((job) => (
          <JobRow key={job.job_id} job={job} online={online} onRetry={onRetry} onDismiss={onDismissJob} />
        ))}
        {visibleVideos.map((video) => (
          <VideoRow
            key={video.video_id}
            video={video}
            addedAt={addedAt[video.video_id]}
            checked={checked}
            onShow={onShowVideo}
            onRemove={onRemoveVideo}
          />
        ))}
      </ul>

      {(hiddenCount > 0 || (expanded && videos.length > COLLAPSED_VIDEO_COUNT)) && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-2 inline-flex w-full items-center justify-center gap-1 rounded-xl py-2 text-sm font-semibold text-slate-500 hover:bg-slate-50"
        >
          {expanded ? '접기' : `영상 ${hiddenCount}개 더 보기`}
          <ChevronDown size={15} className={`transition ${expanded ? 'rotate-180' : ''}`} aria-hidden />
        </button>
      )}
    </section>
  );
}

function JobRow({
  job,
  online,
  onRetry,
  onDismiss,
}: {
  job: AnalysisJob;
  online: boolean;
  onRetry: (job: AnalysisJob) => void;
  onDismiss: (jobId: string) => void;
}) {
  const elapsed = useElapsedSeconds(job.created_at, isActiveJob(job));

  if (job.status === 'failed') {
    const retryable = !NON_RETRYABLE_CODES.has(job.error_code ?? 0);
    return (
      <li className="rounded-2xl bg-red-50 p-3 ring-1 ring-red-100">
        <div className="flex items-start gap-2">
          <AlertCircle size={17} className="mt-0.5 shrink-0 text-red-500" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-bold text-red-900">분석하지 못했어요</p>
            <p className="mt-0.5 text-[13px] leading-snug text-red-800">{job.error || '알 수 없는 오류가 발생했어요.'}</p>
            <p className="mt-1 truncate text-[11px] text-red-700/70">
              {platformLabel(job.source_url)} · {job.source_url}
            </p>
          </div>
          <button
            type="button"
            onClick={() => onDismiss(job.job_id)}
            className="rounded-full p-1 text-red-400 hover:bg-red-100"
            aria-label="실패한 분석 닫기"
          >
            <X size={16} />
          </button>
        </div>
        {retryable && (
          <button
            type="button"
            onClick={() => onRetry(job)}
            disabled={!online}
            className="mt-2 inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-white py-2 text-sm font-bold text-red-700 ring-1 ring-red-200 transition active:scale-[0.98] disabled:opacity-50"
          >
            <RotateCw size={14} aria-hidden />
            다시 시도
          </button>
        )}
      </li>
    );
  }

  const index = Math.max(
    0,
    STAGES.findIndex((s) => s.stage === job.stage),
  );
  const current = STAGES[index];
  const Icon = current.icon;
  // 단계 기반 진행률 + 단계 안에서도 조금씩 차오르도록 (멈춘 것처럼 보이지 않게)
  const base = (index / STAGES.length) * 100;
  const within = (1 - Math.exp(-elapsed / 40)) * (100 / STAGES.length) * 0.9;
  const progress = Math.min(97, Math.round(base + within));

  return (
    <li className="rounded-2xl bg-brand-50/60 p-3 ring-1 ring-brand-100" aria-live="polite">
      <div className="flex items-start gap-2.5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-brand-600 shadow-sm">
          <Icon size={18} className={current.icon === LoaderCircle ? 'animate-spin' : 'animate-pulse'} aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold text-slate-900">{current.label}</p>
          <p className="mt-0.5 truncate text-[11px] text-slate-500">
            {platformLabel(job.source_url)} · {formatElapsed(elapsed)} 경과
          </p>
        </div>
        <button
          type="button"
          onClick={() => onDismiss(job.job_id)}
          className="rounded-full p-1 text-slate-400 hover:bg-white"
          aria-label="이 분석을 목록에서 빼기"
          title="목록에서 빼기 (서버 분석은 끝까지 진행되고, 같은 링크를 다시 넣으면 바로 열려요)"
        >
          <X size={16} />
        </button>
      </div>
      <div
        className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-white"
        role="progressbar"
        aria-label="분석 진행률"
        aria-valuenow={progress}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="h-full rounded-full bg-brand-500 transition-[width] duration-700" style={{ width: `${progress}%` }} />
      </div>
      <ol className="mt-2 flex justify-between text-[10px] font-medium text-slate-400" aria-hidden>
        {STAGES.slice(1).map((s, i) => (
          <li key={s.stage} className={i + 1 <= index ? 'text-brand-700' : ''}>
            {['가져오기', 'AI 분석', '스틸컷', '저장'][i]}
          </li>
        ))}
      </ol>
    </li>
  );
}

function VideoRow({
  video,
  addedAt,
  checked,
  onShow,
  onRemove,
}: {
  video: VideoAnalysisResponse;
  addedAt: number | undefined;
  checked: Record<string, boolean>;
  onShow: (videoId: string) => void;
  onRemove: (videoId: string) => void;
}) {
  const done = video.items.filter((i) => checked[i.id]).length;
  const title = video.source_title || '제목 없는 영상';
  const allDone = done === video.items.length && video.items.length > 0;
  // 대표 이미지 → 첫 상품 썸네일
  const cover =
    video.thumb_url || video.items.find((i) => i.thumb_url || i.image_url)?.thumb_url || video.items.find((i) => i.image_url)?.image_url;
  const [coverFailed, setCoverFailed] = useState(false);
  return (
    <li className="flex items-center gap-2 rounded-2xl p-2 ring-1 ring-slate-100">
      <button
        type="button"
        onClick={() => onShow(video.video_id)}
        className="flex min-w-0 flex-1 items-start gap-2.5 rounded-xl p-1 text-left hover:bg-slate-50"
        aria-label={`${title} 상품 보기`}
      >
        <span className="relative h-16 w-12 shrink-0 overflow-hidden rounded-lg bg-slate-100 text-slate-400">
          {cover && !coverFailed ? (
            <img
              src={cover}
              alt=""
              loading="lazy"
              decoding="async"
              onError={() => setCoverFailed(true)}
              className={`h-full w-full object-cover ${allDone ? 'opacity-60' : ''}`}
            />
          ) : (
            <span className="flex h-full w-full items-center justify-center">
              <ListVideo size={16} aria-hidden />
            </span>
          )}
          {allDone && (
            <span className="absolute inset-0 flex items-center justify-center">
              <CircleCheck size={20} className="rounded-full bg-white text-brand-600" aria-label="모두 담음" />
            </span>
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-bold text-slate-900">{title}</span>
          {video.summary && (
            <span className="mt-0.5 line-clamp-2 block text-xs leading-snug text-slate-600">{video.summary}</span>
          )}
          <span className="mt-0.5 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] text-slate-500">
            <span>{platformLabel(video.source_url)}</span>
            {video.creator_name && <span className="max-w-[9rem] truncate">· {video.creator_name}</span>}
            <span>
              · 상품 {video.items.length}개{done > 0 ? ` (${done}개 담음)` : ''}
            </span>
            {addedAt && <span>· {formatRelativeTime(addedAt)}</span>}
            {video.is_locked ? (
              <span className="inline-flex items-center gap-0.5 rounded-full bg-brand-50 px-1.5 py-px text-[10px] font-bold text-brand-700">
                <Lock size={9} aria-hidden /> 검증 완료
              </span>
            ) : (
              <span className="inline-flex items-center gap-0.5 rounded-full bg-violet-50 px-1.5 py-px text-[10px] font-bold text-violet-700">
                <Sparkles size={9} aria-hidden /> 검증 {video.analysis_count}/5
              </span>
            )}
          </span>
        </span>
      </button>
      {video.source_url && (
        <a
          href={video.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          aria-label={`${title} 원본 영상 열기`}
        >
          <ExternalLink size={15} />
        </a>
      )}
      <button
        type="button"
        onClick={() => {
          if (window.confirm(`'${title}' 영상과 상품을 리스트에서 뺄까요?`)) onRemove(video.video_id);
        }}
        className="rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-red-500"
        aria-label={`${title} 영상을 리스트에서 삭제`}
      >
        <Trash2 size={15} />
      </button>
    </li>
  );
}

function useElapsedSeconds(isoStart: string, running: boolean): number {
  const start = Date.parse(isoStart);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [running]);
  // 기기 시계가 서버보다 느려도 음수가 되지 않게
  return Number.isNaN(start) ? 0 : Math.max(0, (now - start) / 1000);
}

function formatElapsed(sec: number): string {
  const s = Math.floor(sec);
  if (s < 60) return `${s}초`;
  return `${Math.floor(s / 60)}분 ${s % 60}초`;
}
