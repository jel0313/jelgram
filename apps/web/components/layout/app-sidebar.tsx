"use client";

import { HomeIcon, SparklesIcon, SquarePlusIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/auth-provider";
import { useChat } from "@/components/chat/chat-provider";
import { Logo } from "@/components/common/logo";
import { PhaseBadge } from "@/components/common/phase-badge";
import { UserAvatar } from "@/components/common/user-avatar";
import { cn } from "@/lib/utils";

import { UserMenu } from "./user-menu";

/** タイムラインの投稿フォームの入力欄(「投稿する」でフォーカスする) */
export const COMPOSER_INPUT_ID = "composer-input";

/** 「投稿する」:タイムラインの投稿フォームへ(ほかの画面からは、タイムラインに移ってから) */
function useStartCompose() {
  const router = useRouter();
  const pathname = usePathname();
  return () => {
    if (pathname !== "/") {
      router.push("/?compose=1");
      return;
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
    document.getElementById(COMPOSER_INPUT_ID)?.focus({ preventScroll: true });
  };
}

/** PC の左の列(ロゴ・メニュー・ユーザー)。md はアイコンだけ、xl は文字も出す */
export function AppSidebar() {
  const { user } = useAuth();
  const { openChat } = useChat();
  const pathname = usePathname();
  const startCompose = useStartCompose();
  const myPage = `/users/${user?.id}`;

  const itemClass = (active = false) =>
    cn(
      "group flex w-full items-center gap-4 rounded-xl p-3 text-[15px] transition-colors hover:bg-accent xl:px-3",
      active ? "font-bold" : "font-normal",
    );
  const iconClass = "size-6.5 shrink-0 transition-transform group-hover:scale-105 group-active:scale-95";

  return (
    <aside className="sticky top-0 hidden h-dvh w-[76px] shrink-0 flex-col border-r bg-sidebar px-3 pt-8 pb-5 md:flex xl:w-60">
      <Link href="/" className="mb-8 flex h-10 items-center px-2" aria-label="ホーム">
        <Logo className="hidden text-[34px] xl:inline-block" />
        <span className="bg-brand flex size-9 items-center justify-center rounded-xl font-display text-2xl text-white italic xl:hidden">
          j
        </span>
      </Link>

      <nav className="flex flex-1 flex-col gap-1">
        <Link href="/" className={itemClass(pathname === "/")} title="ホーム">
          <HomeIcon className={iconClass} strokeWidth={pathname === "/" ? 2.6 : 1.8} />
          <span className="hidden xl:inline">ホーム</span>
        </Link>
        <button type="button" onClick={startCompose} className={itemClass()} title="投稿する">
          <SquarePlusIcon className={iconClass} strokeWidth={1.8} />
          <span className="hidden xl:inline">投稿する</span>
        </button>
        <button type="button" onClick={openChat} className={cn(itemClass(), "lg:hidden")} title="AI チャット">
          <SparklesIcon className={iconClass} strokeWidth={1.8} />
          <span className="hidden xl:inline">AI チャット</span>
        </button>
        <Link href={myPage} className={itemClass(pathname === myPage)} title="プロフィール">
          <UserAvatar
            name={user?.display_name ?? ""}
            src={user?.avatar_url ?? null}
            size="sm"
            className={cn(
              "size-6.5 transition-transform group-hover:scale-105",
              pathname === myPage && "ring-2 ring-foreground ring-offset-2 ring-offset-sidebar",
            )}
          />
          <span className="hidden xl:inline">プロフィール</span>
          <PhaseBadge phase="4次" className="hidden xl:inline-flex" />
        </Link>
      </nav>

      <UserMenu />
    </aside>
  );
}

/** スマホの上のバー(ロゴ・ユーザー) */
export function MobileHeader() {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border/60 bg-background/80 px-4 backdrop-blur-xl md:hidden">
      <Link href="/" aria-label="ホーム">
        <Logo className="text-[28px]" />
      </Link>
      <UserMenu compact />
    </header>
  );
}

/** スマホの下のタブ(ホーム・投稿する・AI・プロフィール) */
export function MobileTabBar() {
  const { user } = useAuth();
  const { openChat } = useChat();
  const pathname = usePathname();
  const startCompose = useStartCompose();
  const myPage = `/users/${user?.id}`;
  const tabClass = "flex flex-1 items-center justify-center py-3 transition-transform active:scale-90";

  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 flex border-t border-border/60 bg-background/85 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl md:hidden">
      <Link href="/" className={tabClass} aria-label="ホーム">
        <HomeIcon className="size-6.5" strokeWidth={pathname === "/" ? 2.6 : 1.8} />
      </Link>
      <button type="button" onClick={startCompose} className={tabClass} aria-label="投稿する">
        <SquarePlusIcon className="size-6.5" strokeWidth={1.8} />
      </button>
      <button type="button" onClick={openChat} className={tabClass} aria-label="AI チャットを開く">
        <span className="bg-brand flex size-8 items-center justify-center rounded-xl text-white shadow-md shadow-pink-500/25">
          <SparklesIcon className="size-4.5" />
        </span>
      </button>
      <Link href={myPage} className={tabClass} aria-label="プロフィール">
        <UserAvatar
          name={user?.display_name ?? ""}
          src={user?.avatar_url ?? null}
          size="sm"
          className={cn("size-6.5", pathname === myPage && "ring-2 ring-foreground ring-offset-2 ring-offset-background")}
        />
      </Link>
    </nav>
  );
}
