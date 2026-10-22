"use client";

import { LogOutIcon, MenuIcon, PencilIcon, UserIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/auth-provider";
import { PhaseBadge } from "@/components/common/phase-badge";
import { UserAvatar } from "@/components/common/user-avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

/** ログイン中のユーザーと、ログアウトのメニュー(compact:スマホの上のバー用) */
export function UserMenu({ compact = false }: { compact?: boolean }) {
  const { user, signOut } = useAuth();
  const router = useRouter();
  if (!user) return null;

  const handleSignOut = async () => {
    await signOut();
    router.replace("/login");
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "group flex items-center gap-4 rounded-xl text-left transition-colors hover:bg-accent data-[state=open]:bg-accent",
          compact ? "p-1.5" : "w-full p-3",
        )}
        aria-label="メニュー"
      >
        {compact ? (
          <UserAvatar name={user.display_name} src={user.avatar_url} size="sm" className="size-7" />
        ) : (
          <>
            <MenuIcon className="size-6.5 shrink-0" strokeWidth={1.8} />
            <span className="hidden min-w-0 flex-1 xl:block">
              <span className="block truncate text-[15px]">その他</span>
            </span>
          </>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align={compact ? "end" : "start"}
        side={compact ? "bottom" : "top"}
        className="w-64 rounded-2xl p-2"
      >
        <DropdownMenuLabel className="flex items-center gap-3 px-2 py-2">
          <UserAvatar name={user.display_name} src={user.avatar_url} />
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-foreground">{user.display_name}</span>
            {user.email && <span className="block truncate text-xs font-normal">{user.email}</span>}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild className="rounded-lg py-2">
          <Link href={`/users/${user.id}`}>
            <UserIcon />
            プロフィール
            <PhaseBadge phase="4次" className="ml-auto" />
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild className="rounded-lg py-2">
          <Link href="/settings/profile">
            <PencilIcon />
            プロフィールを編集
            <PhaseBadge phase="4次" className="ml-auto" />
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleSignOut} className="rounded-lg py-2">
          <LogOutIcon />
          ログアウト
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
