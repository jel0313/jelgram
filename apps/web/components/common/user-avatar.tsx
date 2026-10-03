import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { initials } from "@/lib/format";

type Props = {
  name: string;
  src: string | null;
  size?: "default" | "sm" | "lg";
  className?: string;
};

/** ユーザーのアイコン。画像がなければ名前の頭文字を出す */
export function UserAvatar({ name, src, size = "default", className }: Props) {
  return (
    <Avatar size={size} className={className}>
      {src && <AvatarImage src={src} alt="" />}
      <AvatarFallback>{initials(name)}</AvatarFallback>
    </Avatar>
  );
}
