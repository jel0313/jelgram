import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { initials } from "@/lib/format";
import { cn } from "@/lib/utils";

type Props = {
  name: string;
  src: string | null;
  size?: "default" | "sm" | "lg";
  /** インスタのストーリーのような、グラデーションの輪で囲む */
  ring?: boolean;
  className?: string;
};

/** ユーザーのアイコン。画像がなければ名前の頭文字を出す */
export function UserAvatar({ name, src, size = "default", ring = false, className }: Props) {
  const avatar = (
    <Avatar size={size} className={cn(!ring && className, ring && "size-full!")}>
      {src && <AvatarImage src={src} alt="" />}
      <AvatarFallback className="bg-linear-to-br from-muted to-accent text-[length:inherit] font-semibold text-foreground/70">
        {initials(name)}
      </AvatarFallback>
    </Avatar>
  );
  if (!ring) return avatar;

  // 輪(グラデーション)→ 白い隙間 → アイコン の 3 重にする
  return (
    <span className={cn("bg-brand inline-flex shrink-0 rounded-full p-[2px]", className)}>
      <span className="flex size-full rounded-full bg-card p-[2px]">{avatar}</span>
    </span>
  );
}
