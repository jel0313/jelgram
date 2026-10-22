"use client";

import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";

import { ChatPanel } from "./chat-panel";
import { useChat } from "./chat-provider";

/** スマホ・タブレット用:下から AI チャットを出す(開くのは下のタブや「AI に聞く」。PC では使わない) */
export function MobileChat() {
  const { mobileOpen, setMobileOpen } = useChat();

  return (
    <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
      <SheetContent
        side="bottom"
        showCloseButton={false}
        className="gap-0 overflow-hidden rounded-t-3xl p-0 data-[side=bottom]:h-[88dvh] lg:hidden"
        // 開いたときに「新しい会話」ボタンへフォーカスが当たって、ツールチップが出ないようにする
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <SheetTitle className="sr-only">AI チャット</SheetTitle>
        <SheetDescription className="sr-only">AI と会話する</SheetDescription>
        <div className="mx-auto mt-2 h-1 w-10 shrink-0 rounded-full bg-muted-foreground/30" aria-hidden />
        <ChatPanel />
      </SheetContent>
    </Sheet>
  );
}
