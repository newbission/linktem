import type { VideoAnalysisResponse } from '@linktem/types';

import { groupEntries, toEntries } from './grouping';
import { itemNumbers } from './numbering';

export interface ExportOptions {
  /** 체크하지 않은 항목만 */
  remainingOnly: boolean;
  /** 헷갈리지 말 점 / 추천 이유 메모 포함 */
  includeNotes: boolean;
}

/**
 * 카카오톡·메모앱 등에 붙여넣을 수 있는 텍스트 체크리스트.
 * 마트에서 바로 쓰기 좋도록 판매처별로 묶는다.
 */
export function formatListText(
  videos: VideoAnalysisResponse[],
  checked: Record<string, boolean>,
  options: ExportOptions,
  siteUrl?: string,
): string {
  const all = toEntries(videos, checked);
  const numbers = itemNumbers(videos);
  const entries = options.remainingOnly ? all.filter((e) => !e.item.is_checked) : all;
  const done = all.filter((e) => e.item.is_checked).length;

  const lines: string[] = [`🛒 장보기 리스트 (${done}/${all.length} 담음)`];
  if (entries.length === 0) {
    lines.push('', '모두 담았어요! 🎉');
  }

  for (const group of groupEntries(entries, 'retailer')) {
    lines.push('', `[${group.title}]`);
    for (const { item } of group.entries) {
      const note = item.edition_note ? ` (${item.edition_note})` : '';
      lines.push(`${item.is_checked ? '☑' : '☐'} ${numbers[item.id]}. ${item.name_ko}${note}`);
      if (options.includeNotes) {
        if (item.caution) lines.push(`   ⚠️ ${item.caution}`);
        if (item.reason) lines.push(`   💬 ${item.reason}`);
      }
    }
  }

  const sources = videos.filter((v) => entries.some((e) => e.video.video_id === v.video_id));
  if (sources.length > 0) {
    lines.push('', '📺 참고 영상');
    for (const v of sources) {
      const title = [v.source_title, v.creator_name].filter(Boolean).join(' - ') || '영상';
      lines.push(`· ${title}${v.source_url ? `\n  ${v.source_url}` : ''}`);
    }
  }

  lines.push('', `Linktem 으로 만든 리스트${siteUrl ? ` · ${siteUrl}` : ''}`);
  return lines.join('\n');
}

/** 클립보드 복사 — 비보안 컨텍스트/구형 브라우저용 execCommand 폴백 포함 */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* 폴백으로 진행 */
  }
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  try {
    return document.execCommand('copy');
  } catch {
    return false;
  } finally {
    document.body.removeChild(textarea);
  }
}
