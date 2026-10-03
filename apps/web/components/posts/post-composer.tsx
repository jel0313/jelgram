"use client";

import { ImageIcon, Loader2Icon, XIcon } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { UserAvatar } from "@/components/common/user-avatar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/lib/api/errors";
import { createPost } from "@/lib/api/posts";
import type { Post } from "@/lib/api/types";
import { uploadImage } from "@/lib/api/uploads";
import { CONTENT_MAX_LENGTH, IMAGE_ACCEPT_TYPES, IMAGE_MAX_BYTES } from "@/lib/constants";
import { cn } from "@/lib/utils";

type Props = {
  /** 投稿できたら、タイムラインの先頭に足す */
  onCreated: (post: Post) => void;
};

/** 投稿フォーム(本文 + 画像 1 枚) */
export function PostComposer({ onCreated }: Props) {
  const { user } = useAuth();
  const [content, setContent] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const length = content.trim().length;
  const tooLong = length > CONTENT_MAX_LENGTH;
  const canSubmit = length > 0 && !tooLong && !submitting;

  const selectImage = (file: File | undefined) => {
    if (!file) return;
    if (!IMAGE_ACCEPT_TYPES.includes(file.type)) {
      toast.error("画像は JPEG・PNG・WebP・GIF のどれかにしてください");
      return;
    }
    if (file.size > IMAGE_MAX_BYTES) {
      toast.error("画像は 5MB 以下にしてください");
      return;
    }
    setImage(file);
    setPreview(URL.createObjectURL(file));
  };

  const removeImage = () => {
    setImage(null);
    setPreview(null);
    if (fileInput.current) fileInput.current.value = "";
  };

  const submit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const imageUrl = image ? await uploadImage(image) : null;
      const post = await createPost({ content: content.trim(), image_url: imageUrl });
      onCreated(post);
      setContent("");
      removeImage();
      toast.success("投稿しました");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      className="flex gap-3 border-b px-4 py-4"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <UserAvatar name={user?.display_name ?? ""} src={user?.avatar_url ?? null} size="lg" />
      <div className="min-w-0 flex-1 space-y-3">
        <Textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="いまどうしてる?"
          rows={3}
          className="resize-none border-none px-0 text-base shadow-none focus-visible:ring-0"
        />
        {preview && (
          <div className="relative w-fit">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={preview} alt="選んだ画像" className="max-h-64 rounded-xl border object-cover" />
            <Button
              type="button"
              size="icon-sm"
              variant="secondary"
              className="absolute top-2 right-2 rounded-full"
              onClick={removeImage}
              aria-label="画像を外す"
            >
              <XIcon />
            </Button>
          </div>
        )}
        <div className="flex items-center justify-between border-t pt-3">
          <input
            ref={fileInput}
            type="file"
            accept={IMAGE_ACCEPT_TYPES.join(",")}
            className="hidden"
            onChange={(e) => selectImage(e.target.files?.[0])}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="text-violet-600 hover:text-violet-700"
            onClick={() => fileInput.current?.click()}
            disabled={submitting}
            aria-label="画像を選ぶ"
          >
            <ImageIcon className="size-5" />
          </Button>
          <div className="flex items-center gap-3">
            <span className={cn("text-xs tabular-nums text-muted-foreground", tooLong && "text-destructive")}>
              {length} / {CONTENT_MAX_LENGTH}
            </span>
            <Button type="submit" disabled={!canSubmit} className="rounded-full px-5">
              {submitting && <Loader2Icon className="animate-spin" />}
              投稿する
            </Button>
          </div>
        </div>
      </div>
    </form>
  );
}
