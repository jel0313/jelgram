"use client";

import { HomeIcon, UserIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/auth/auth-provider";
import { Logo } from "@/components/common/logo";
import { PhaseBadge } from "@/components/common/phase-badge";
import { cn } from "@/lib/utils";

import { UserMenu } from "./user-menu";

/** PC の左の列(ロゴ・メニュー・ユーザー) */
export function AppSidebar() {
  const { user } = useAuth();
  const pathname = usePathname();
  const myPage = `/users/${user?.id}`;
  const navClass = (active: boolean) =>
    cn(
      "flex items-center gap-3 rounded-full px-3 py-2.5 text-lg transition-colors hover:bg-accent",
      active && "font-bold",
    );

  return (
    <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col justify-between border-r px-4 py-6 md:flex">
      <div className="space-y-6">
        <Link href="/" className="block px-3">
          <Logo />
        </Link>
        <nav className="space-y-1">
          <Link href="/" className={navClass(pathname === "/")}>
            <HomeIcon className="size-6" />
            ホーム
          </Link>
          <Link href={myPage} className={navClass(pathname === myPage)}>
            <UserIcon className="size-6" />
            プロフィール
            <PhaseBadge phase="4次" />
          </Link>
        </nav>
      </div>
      <UserMenu />
    </aside>
  );
}

/** スマホの上のバー(ロゴ・ユーザー) */
export function MobileHeader() {
  return (
    <header className="sticky top-0 z-30 flex items-center justify-between border-b bg-background/90 px-4 py-2 backdrop-blur md:hidden">
      <Link href="/">
        <Logo className="text-xl" />
      </Link>
      <UserMenu compact />
    </header>
  );
}
