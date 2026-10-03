import { cn } from "@/lib/utils";

/** jelgram のロゴ */
export function Logo({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "bg-linear-to-r from-violet-500 to-pink-500 bg-clip-text font-heading text-2xl font-bold tracking-tight text-transparent",
        className,
      )}
    >
      jelgram
    </span>
  );
}
