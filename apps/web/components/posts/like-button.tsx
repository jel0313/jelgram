"use client";

import { HeartIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { errorMessage } from "@/lib/api/errors";
import { likePost, unlikePost } from "@/lib/api/posts";
import type { Post } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type Props = {
  post: Post;
  /** いいねの結果を、投稿一覧に反映する */
  onChange: (postId: number, likeCount: number, likedByMe: boolean) => void;
};

/** いいねボタン。いいね済みならもう一度押すと取り消し */
export function LikeButton({ post, onChange }: Props) {
  const [pending, setPending] = useState(false);

  const toggle = async () => {
    setPending(true);
    try {
      const result = post.liked_by_me ? await unlikePost(post.id) : await likePost(post.id);
      onChange(result.post_id, result.like_count, result.liked_by_me);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setPending(false);
    }
  };

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={pending}
      aria-pressed={post.liked_by_me}
      aria-label={post.liked_by_me ? "いいねを取り消す" : "いいねする"}
      className={cn(
        "group flex items-center gap-1.5 rounded-full px-2 py-1 text-sm transition-colors disabled:opacity-60",
        post.liked_by_me ? "text-pink-600" : "text-muted-foreground hover:text-pink-600",
      )}
    >
      <HeartIcon
        className={cn(
          "size-4.5 transition-transform group-active:scale-90",
          post.liked_by_me && "fill-current",
        )}
      />
      <span className="tabular-nums">{post.like_count}</span>
    </button>
  );
}
