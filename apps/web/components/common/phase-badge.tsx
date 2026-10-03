import { cn } from "@/lib/utils";

/**
 * 1次(MVP)より後のフェーズで API につなぐ機能に付ける印(要件定義書 12.2)。
 * 例:<PhaseBadge phase="4次" />
 */
export function PhaseBadge({ phase, className }: { phase: string; className?: string }) {
  return (
    <span
      title={`${phase}開発で API につなぐ機能`}
      className={cn(
        "inline-flex shrink-0 items-center rounded-full border border-dashed border-amber-400 px-1.5 text-[10px] leading-4 font-medium text-amber-600 dark:text-amber-400",
        className,
      )}
    >
      {phase}
    </span>
  );
}
