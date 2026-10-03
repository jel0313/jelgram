"use client";

import { Loader2Icon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ChatProvider } from "@/components/chat/chat-provider";
import { MobileChat } from "@/components/chat/mobile-chat";
import { AppSidebar, MobileHeader } from "@/components/layout/app-sidebar";

/** ログイン後の画面の共通レイアウト(左:メニュー / 中央:ページ / 右:AI チャット) */
export default function MainLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  // 全機能ログイン必須(要件定義書 3.1):未ログインならログイン画面へ
  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex h-dvh items-center justify-center">
        <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <ChatProvider>
      <div className="mx-auto flex min-h-dvh max-w-7xl">
        <AppSidebar />
        <main className="min-w-0 flex-1 border-r">
          <MobileHeader />
          {children}
        </main>
        <aside className="sticky top-0 hidden h-dvh w-96 shrink-0 lg:block">
          <ChatPanel />
        </aside>
      </div>
      <MobileChat />
    </ChatProvider>
  );
}
