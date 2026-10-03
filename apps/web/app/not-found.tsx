import Link from "next/link";

import { Logo } from "@/components/common/logo";
import { Button } from "@/components/ui/button";

/** 存在しないページ */
export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-4 text-center">
      <Logo />
      <p className="text-muted-foreground">ページが見つかりません</p>
      <Button asChild variant="outline">
        <Link href="/">ホームに戻る</Link>
      </Button>
    </main>
  );
}
