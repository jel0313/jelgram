"use client";

import { LogOutIcon, PencilIcon, UserIcon } from "lucide-react";
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

/** ログイン中のユーザーと、ログアウトのメニュー */
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
          "flex items-center gap-3 rounded-full text-left transition-colors hover:bg-accent",
          compact ? "p-1" : "w-full p-2",
        )}
      >
        <UserAvatar name={user.display_name} src={user.avatar_url} />
        {!compact && (
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold">{user.display_name}</span>
            <span className="block truncate text-xs text-muted-foreground">{user.email}</span>
          </span>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align={compact ? "end" : "start"} className="w-56">
        <DropdownMenuLabel className="truncate">{user.display_name}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href={`/users/${user.id}`}>
            <UserIcon />
            プロフィール
            <PhaseBadge phase="4次" className="ml-auto" />
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/settings/profile">
            <PencilIcon />
            プロフィールを編集
            <PhaseBadge phase="4次" className="ml-auto" />
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleSignOut}>
          <LogOutIcon />
          ログアウト
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
