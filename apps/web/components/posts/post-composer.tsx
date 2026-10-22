"use client";

import { ImagePlusIcon, Loader2Icon, XIcon } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { UserAvatar } from "@/components/common/user-avatar";
import { COMPOSER_INPUT_ID } from "@/components/layout/app-sidebar";
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
      className="border-b border-border/60 bg-card px-4 py-4 md:mb-6 md:rounded-3xl md:border md:border-border/70 md:shadow-[0_2px_16px_-8px_rgb(0_0_0/0.08)]"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <div className="flex gap-3">
        <UserAvatar name={user?.display_name ?? ""} src={user?.avatar_url ?? null} className="size-10" />
        <div className="min-w-0 flex-1 space-y-3">
          <Textarea
            id={COMPOSER_INPUT_ID}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="いまどうしてる?"
            rows={1}
            aria-label="投稿の本文"
            className="max-h-72 min-h-10 resize-none rounded-none border-none bg-transparent px-0 py-2 text-base shadow-none md:text-base focus-visible:ring-0 dark:bg-transparent"
          />
          {preview && (
            <div className="relative w-fit overflow-hidden rounded-2xl">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={preview} alt="選んだ画像" className="max-h-72 object-cover" />
              <button
                type="button"
                className="absolute top-2 right-2 flex size-7 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur transition-colors hover:bg-black/80"
                onClick={removeImage}
                aria-label="画像を外す"
              >
                <XIcon className="size-4" />
              </button>
            </div>
          )}
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between pl-13">
        <input
          ref={fileInput}
          type="file"
          accept={IMAGE_ACCEPT_TYPES.join(",")}
          className="hidden"
          onChange={(e) => selectImage(e.target.files?.[0])}
        />
        <button
          type="button"
          className="-ml-2 flex items-center gap-1.5 rounded-full px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-50"
          onClick={() => fileInput.current?.click()}
          disabled={submitting}
          aria-label="画像を選ぶ"
        >
          <ImagePlusIcon className="size-5" strokeWidth={1.8} />
          <span className="hidden sm:inline">写真</span>
        </button>
        <div className="flex items-center gap-3">
          {length > 0 && (
            <span className={cn("text-xs tabular-nums text-muted-foreground", tooLong && "font-semibold text-destructive")}>
              {length} / {CONTENT_MAX_LENGTH}
            </span>
          )}
          <Button
            type="submit"
            disabled={!canSubmit}
            className="bg-brand h-9 rounded-full px-5 font-semibold text-white shadow-md shadow-pink-500/20 transition-[opacity,transform] hover:opacity-90 disabled:bg-none disabled:bg-muted disabled:text-muted-foreground disabled:opacity-100 disabled:shadow-none"
          >
            {submitting && <Loader2Icon className="animate-spin" />}
            投稿する
          </Button>
        </div>
      </div>
    </form>
  );
}
