"use client";

import { ErrorState } from "@/components/common/error-state";

/** 予期しないエラーが起きたときの画面 */
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="flex min-h-dvh items-center justify-center">
      <ErrorState message="問題が発生しました。もう一度お試しください" onRetry={reset} />
    </main>
  );
}
