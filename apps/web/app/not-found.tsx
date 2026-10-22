import Link from "next/link";

import { Logo } from "@/components/common/logo";
import { Button } from "@/components/ui/button";

/** 存在しないページ */
export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-5 px-4 text-center">
      <Logo className="text-5xl" />
      <div className="space-y-1.5">
        <p className="text-xl font-bold">ページが見つかりません</p>
        <p className="text-sm text-muted-foreground">リンクが壊れているか、ページが削除された可能性があります</p>
      </div>
      <Button asChild className="h-10 rounded-full px-6 font-semibold">
        <Link href="/">ホームに戻る</Link>
      </Button>
    </main>
  );
}
