'use client';

import { useEffect, useRef } from 'react';

import type { AnalysisJob, VideoAnalysisResponse } from '@linktem/types';

import { ApiError, getJob } from './api';

const POLL_INTERVAL_MS = 2_500;

export function isActiveJob(job: AnalysisJob): boolean {
  return job.status === 'queued' || job.status === 'running';
}

interface Handlers {
  onProgress: (job: AnalysisJob) => void;
  onDone: (job: AnalysisJob, video: VideoAnalysisResponse) => void;
  onFailed: (job: AnalysisJob) => void;
}

/**
 * 진행 중인 분석 작업을 짧은 요청으로 주기 조회한다.
 * - 요청 하나가 몇 분씩 열려 있지 않으므로 화면 꺼짐·앱 전환·네트워크 변경으로 연결이 끊겨도 다음 조회에서 이어진다.
 * - 탭이 숨겨진 동안은 쉬고, 다시 보이거나 온라인이 되면 즉시 조회한다.
 * - 작업 목록은 localStorage 에 있으므로 앱을 닫았다 열어도 같은 작업을 이어서 조회한다.
 */
export function useJobPolling(jobs: AnalysisJob[], enabled: boolean, handlers: Handlers): void {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;
  const jobsRef = useRef(jobs);
  jobsRef.current = jobs;
  const activeKey = jobs
    .filter(isActiveJob)
    .map((j) => j.job_id)
    .join(',');

  useEffect(() => {
    if (!enabled || !activeKey) return;
    let stopped = false;
    let inFlight = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const schedule = () => {
      if (!stopped) timer = setTimeout(poll, POLL_INTERVAL_MS);
    };

    async function poll(): Promise<void> {
      if (stopped || inFlight) return;
      if (document.visibilityState === 'hidden') {
        schedule();
        return;
      }
      inFlight = true;
      const active = jobsRef.current.filter(isActiveJob);
      await Promise.all(
        active.map(async (job) => {
          try {
            const res = await getJob(job.job_id);
            if (stopped || !res.job) return;
            if (res.job.status === 'done' && res.video) handlersRef.current.onDone(res.job, res.video);
            else if (res.job.status === 'failed') handlersRef.current.onFailed(res.job);
            else if (res.job.stage !== job.stage || res.job.status !== job.status) handlersRef.current.onProgress(res.job);
          } catch (err) {
            if (!stopped && err instanceof ApiError && err.status === 404) {
              // 오래된 작업 기록이 정리된 경우
              handlersRef.current.onFailed({
                ...job,
                status: 'failed',
                stage: 'failed',
                error: '분석 기록을 찾을 수 없어요. 링크를 다시 넣어 주세요.',
                error_code: 404,
              });
            }
            // 네트워크 오류·서버 재시작 중에는 다음 주기에 다시 조회
          }
        }),
      );
      inFlight = false;
      schedule();
    }

    const resume = () => {
      if (document.visibilityState !== 'visible') return;
      clearTimeout(timer);
      void poll();
    };

    void poll();
    document.addEventListener('visibilitychange', resume);
    window.addEventListener('online', resume);
    return () => {
      stopped = true;
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', resume);
      window.removeEventListener('online', resume);
    };
  }, [enabled, activeKey]);
}
