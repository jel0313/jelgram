/** 投稿日時を「3分前」「2時間前」「9月28日」のように表示する */
export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (seconds < 60) return "たった今";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}分前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}時間前`;
  const sameYear = date.getFullYear() === now.getFullYear();
  return sameYear
    ? `${date.getMonth() + 1}月${date.getDate()}日`
    : `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

/** 名前の頭文字(アイコンがない人の代わりの表示) */
export function initials(name: string): string {
  return name.slice(0, 1).toUpperCase();
}

/** 日時をそのまま表示する(例:2026年9月28日 12:15) */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const time = `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ${time}`;
}

/** 年月を表示する(例:2026年9月) */
export function formatYearMonth(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}年${d.getMonth() + 1}月`;
}
