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

/** いいねボタン(ハートだけ。数は投稿の下に出す)。いいね済みならもう一度押すと取り消し */
export function LikeButton({ post, onChange }: Props) {
  const [pending, setPending] = useState(false);
  // いいねした瞬間だけ、ハートをふくらませる
  const [popped, setPopped] = useState(false);

  const toggle = async () => {
    setPending(true);
    try {
      const result = post.liked_by_me ? await unlikePost(post.id) : await likePost(post.id);
      setPopped(result.liked_by_me);
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
      className="group -m-1.5 rounded-full p-1.5 transition-opacity disabled:opacity-60"
    >
      <HeartIcon
        className={cn(
          "size-6.5 transition-[transform,color] group-hover:opacity-60 group-active:scale-90",
          post.liked_by_me ? "fill-(--like) text-(--like) group-hover:opacity-100" : "text-foreground",
          popped && "animate-like-pop",
        )}
        strokeWidth={1.8}
        onAnimationEnd={() => setPopped(false)}
      />
    </button>
  );
}
