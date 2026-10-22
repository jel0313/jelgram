"use client";

import { CameraIcon, Loader2Icon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { PhaseBadge } from "@/components/common/phase-badge";
import { UserAvatar } from "@/components/common/user-avatar";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { errorMessage } from "@/lib/api/errors";
import { uploadImage } from "@/lib/api/uploads";
import { updateMyProfile } from "@/lib/api/users";
import { DISPLAY_NAME_MAX_LENGTH, IMAGE_ACCEPT_TYPES, IMAGE_MAX_BYTES } from "@/lib/constants";

/** プロフィール編集(表示名・アイコン。4次) */
export default function ProfileSettingsPage() {
  const { user, updateUser } = useAuth();
  const router = useRouter();
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(user?.avatar_url ?? null);
  const [saving, setSaving] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const nameLength = displayName.trim().length;
  const nameError =
    nameLength === 0
      ? "表示名を入力してください"
      : nameLength > DISPLAY_NAME_MAX_LENGTH
        ? `表示名は ${DISPLAY_NAME_MAX_LENGTH} 文字以内にしてください`
        : null;
  const changed = displayName.trim() !== user?.display_name || avatarFile !== null;

  const selectAvatar = (file: File | undefined) => {
    if (!file) return;
    if (!IMAGE_ACCEPT_TYPES.includes(file.type)) {
      toast.error("画像は JPEG・PNG・WebP・GIF のどれかにしてください");
      return;
    }
    if (file.size > IMAGE_MAX_BYTES) {
      toast.error("画像は 5MB 以下にしてください");
      return;
    }
    setAvatarFile(file);
    setAvatarPreview(URL.createObjectURL(file));
  };

  const save = async () => {
    if (nameError || !user) return;
    setSaving(true);
    try {
      const avatarUrl = avatarFile ? await uploadImage(avatarFile) : user.avatar_url;
      const profile = await updateMyProfile({ display_name: displayName.trim(), avatar_url: avatarUrl });
      updateUser({ display_name: profile.display_name, avatar_url: profile.avatar_url });
      toast.success("プロフィールを保存しました");
      router.push(`/users/${user.id}`);
    } catch (error) {
      toast.error(errorMessage(error));
      setSaving(false);
    }
  };

  return (
    <>
      <PageHeader title="プロフィールを編集" back>
        <PhaseBadge phase="4次" />
      </PageHeader>
      <form
        className="mx-4 my-4 space-y-6 rounded-3xl border border-border/70 bg-card p-5 shadow-[0_2px_16px_-8px_rgb(0_0_0/0.08)] md:mx-0 md:p-6"
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <div className="flex items-center gap-4 rounded-2xl bg-muted/70 p-4">
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            className="group relative shrink-0 rounded-full"
            aria-label="アイコンを変更"
          >
            <UserAvatar name={displayName || "?"} src={avatarPreview} ring className="size-16 text-xl" />
            <span className="absolute inset-0 flex items-center justify-center rounded-full bg-black/40 text-white opacity-0 transition-opacity group-hover:opacity-100">
              <CameraIcon className="size-5" />
            </span>
          </button>
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold">{displayName || "表示名"}</p>
            <p className="text-xs text-muted-foreground">JPEG・PNG・WebP・GIF(5MB まで)</p>
          </div>
          <Button
            type="button"
            size="sm"
            className="h-8 rounded-lg px-3 font-semibold"
            onClick={() => fileInput.current?.click()}
          >
            写真を変更
          </Button>
          <input
            ref={fileInput}
            type="file"
            accept={IMAGE_ACCEPT_TYPES.join(",")}
            className="hidden"
            onChange={(e) => selectAvatar(e.target.files?.[0])}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="display-name" className="font-semibold">
            表示名
          </Label>
          <Input
            id="display-name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            aria-invalid={nameError !== null}
            className="h-11 rounded-xl px-3.5"
          />
          <div className="flex justify-between text-xs">
            <span className="text-destructive">{nameError}</span>
            <span className="text-muted-foreground tabular-nums">
              {nameLength} / {DISPLAY_NAME_MAX_LENGTH}
            </span>
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" className="h-10 rounded-full px-5" onClick={() => router.back()}>
            キャンセル
          </Button>
          <Button
            type="submit"
            disabled={!changed || nameError !== null || saving}
            className="bg-brand h-10 rounded-full px-6 font-semibold text-white disabled:bg-none disabled:bg-muted disabled:text-muted-foreground disabled:opacity-100"
          >
            {saving && <Loader2Icon className="animate-spin" />}
            保存する
          </Button>
        </div>
      </form>
    </>
  );
}
