"use client";

import { Loader2Icon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ChatProvider } from "@/components/chat/chat-provider";
import { MobileChat } from "@/components/chat/mobile-chat";
import { AppSidebar, MobileHeader, MobileTabBar } from "@/components/layout/app-sidebar";

/** ログイン後の画面の共通レイアウト(左:メニュー / 中央:ページ / 右:AI チャット。スマホは下にタブ) */
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
      <div className="flex min-h-dvh">
        <AppSidebar />
        <main className="min-w-0 flex-1 pb-[calc(3.5rem+env(safe-area-inset-bottom))] md:pb-0">
          <MobileHeader />
          <div className="mx-auto w-full max-w-[560px] md:px-6 md:pb-10">{children}</div>
        </main>
        <aside className="sticky top-0 hidden h-dvh w-[380px] shrink-0 py-4 pr-4 lg:block xl:w-[400px]">
          <ChatPanel className="overflow-hidden rounded-3xl border bg-card shadow-[0_8px_30px_-12px_rgb(0_0_0/0.12)]" />
        </aside>
      </div>
      <MobileTabBar />
      <MobileChat />
    </ChatProvider>
  );
}
