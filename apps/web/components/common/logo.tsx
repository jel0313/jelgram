import { cn } from "@/lib/utils";

/** jelgram のロゴ(筆記体風の英字 + ブランドのグラデーション) */
export function Logo({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "text-brand inline-block pr-1 font-display text-3xl leading-none tracking-tight italic",
        className,
      )}
    >
      jelgram
    </span>
  );
}
