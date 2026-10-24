import type { VideoAnalysisResponse } from '@linktem/types';

/**
 * 체크리스트 번호 (item.id → 1부터).
 * 먼저 담은 영상부터, 영상 안에서는 등장 순서대로 매긴다 → 새 영상을 담아도, 체크해서 순서가 바뀌어도
 * 기존 번호가 그대로라 "3번 담았어?" 처럼 부르기 좋다. (리스트는 최근 영상이 앞에 있으므로 거꾸로 센다)
 */
export function itemNumbers(videos: VideoAnalysisResponse[]): Record<string, number> {
  const numbers: Record<string, number> = {};
  let n = 0;
  for (let i = videos.length - 1; i >= 0; i -= 1) {
    for (const item of videos[i].items) {
      n += 1;
      numbers[item.id] = n;
    }
  }
  return numbers;
}
