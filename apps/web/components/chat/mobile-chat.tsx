"use client";

import { BotIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";

import { ChatPanel } from "./chat-panel";
import { useChat } from "./chat-provider";

/** スマホ用:右下のボタンで、下から AI チャットを出す(PC では表示しない) */
export function MobileChat() {
  const { mobileOpen, setMobileOpen } = useChat();

  return (
    <div className="lg:hidden">
      <Button
        size="icon-lg"
        className="fixed right-4 bottom-4 z-40 size-14 rounded-full bg-violet-600 shadow-lg hover:bg-violet-700"
        onClick={() => setMobileOpen(true)}
        aria-label="AI チャットを開く"
      >
        <BotIcon className="size-6" />
      </Button>
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent
          side="bottom"
          className="gap-0 p-0 data-[side=bottom]:h-[85dvh]"
          // 開いたときに「新しい会話」ボタンへフォーカスが当たって、ツールチップが出ないようにする
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <SheetTitle className="sr-only">AI チャット</SheetTitle>
          <SheetDescription className="sr-only">AI と会話する</SheetDescription>
          <ChatPanel />
        </SheetContent>
      </Sheet>
    </div>
  );
}
