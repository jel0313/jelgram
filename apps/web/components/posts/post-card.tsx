"use client";

import { SparklesIcon } from "lucide-react";
import Link from "next/link";

import { useAuth } from "@/components/auth/auth-provider";
import { useChat } from "@/components/chat/chat-provider";
import { UserAvatar } from "@/components/common/user-avatar";
import type { Post } from "@/lib/api/types";
import { formatDateTime, formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

import { ImageViewer } from "./image-viewer";
import { LikeButton } from "./like-button";
import { PostMenu } from "./post-menu";

export type PostCardHandlers = {
  onLikeChange: (postId: number, likeCount: number, likedByMe: boolean) => void;
  onUpdated: (post: Post) => void;
  onDeleted: (postId: number) => void;
};

type Props = PostCardHandlers & {
  post: Post;
  /** 投稿詳細画面で使う(本文を省略しない・日時をそのまま表示) */
  detail?: boolean;
};

/** 投稿 1 件(インスタ風:投稿者 → 画像 → いいね・AI → いいね数 → 本文) */
export function PostCard({ post, detail = false, onLikeChange, onUpdated, onDeleted }: Props) {
  const { askAbout } = useChat();
  const { user } = useAuth();
  const isMine = user?.id === post.author.id;
  const userHref = `/users/${post.author.id}`;
  const postHref = `/posts/${post.id}`;
  const hasImage = post.image_url !== null;

  const body = (
    <p
      className={cn(
        "whitespace-pre-wrap break-words",
        hasImage ? "text-sm leading-relaxed" : "text-[17px] leading-relaxed tracking-wide",
        !detail && (hasImage ? "line-clamp-3" : "line-clamp-8"),
      )}
    >
      {hasImage && (
        <Link href={userHref} className="mr-1.5 font-semibold hover:opacity-70">
          {post.author.display_name}
        </Link>
      )}
      {detail ? (
        post.content
      ) : (
        <Link href={postHref} className="hover:opacity-80">
          {post.content}
        </Link>
      )}
    </p>
  );

  return (
    <article className="border-b border-border/60 bg-card pb-4 md:mb-6 md:overflow-hidden md:rounded-3xl md:border md:border-border/70 md:shadow-[0_2px_16px_-8px_rgb(0_0_0/0.08)]">
      <header className="flex items-center gap-3 px-4 py-3">
        <Link href={userHref} className="shrink-0" aria-label={`${post.author.display_name} のページ`}>
          <UserAvatar name={post.author.display_name} src={post.author.avatar_url} ring className="size-10" />
        </Link>
        <div className="flex min-w-0 items-baseline gap-1.5 text-sm">
          <Link href={userHref} className="truncate font-semibold hover:opacity-70">
            {post.author.display_name}
          </Link>
          <span className="text-muted-foreground" aria-hidden>
            ・
          </span>
          {detail ? (
            <time dateTime={post.created_at} className="shrink-0 text-muted-foreground">
              {formatDateTime(post.created_at)}
            </time>
          ) : (
            <Link href={postHref} className="shrink-0 text-muted-foreground hover:text-foreground">
              <time dateTime={post.created_at}>{formatRelativeTime(post.created_at)}</time>
            </Link>
          )}
        </div>
        {isMine && (
          <div className="-my-1 ml-auto">
            <PostMenu post={post} onUpdated={onUpdated} onDeleted={onDeleted} />
          </div>
        )}
      </header>

      {hasImage ? (
        <ImageViewer
          src={post.image_url!}
          className={cn("w-full", detail ? "max-h-[80dvh] object-contain" : "aspect-[4/5] object-cover")}
        />
      ) : (
        <div className="px-4 pb-1">
          {body}
        </div>
      )}

      <div className="flex items-center gap-4 px-4 pt-3">
        <LikeButton post={post} onChange={onLikeChange} />
        <button
          type="button"
          onClick={() => askAbout(post)}
          className="group ml-auto flex items-center gap-1.5 rounded-full border border-border/80 py-1.5 pr-3.5 pl-3 text-xs font-medium transition-colors hover:border-transparent hover:bg-accent"
        >
          <SparklesIcon className="size-3.5 text-(--brand-via) transition-transform group-hover:rotate-12" />
          この投稿について AI に聞く
        </button>
      </div>

      <div className="space-y-1.5 px-4 pt-2.5">
        {post.like_count > 0 ? (
          <p className="text-sm font-semibold tabular-nums">いいね! {post.like_count.toLocaleString()}件</p>
        ) : (
          <p className="text-sm text-muted-foreground">最初のいいねをしよう</p>
        )}
        {hasImage && body}
      </div>
    </article>
  );
}

/** 読み込み中の投稿の形 */
export function PostCardSkeleton() {
  return (
    <div className="border-b border-border/60 bg-card pb-4 md:mb-6 md:overflow-hidden md:rounded-3xl md:border md:border-border/70">
      <div className="flex items-center gap-3 px-4 py-3">
        <div className="size-10 shrink-0 animate-pulse rounded-full bg-muted" />
        <div className="h-3.5 w-32 animate-pulse rounded-full bg-muted" />
      </div>
      <div className="aspect-[4/3] w-full animate-pulse bg-muted" />
      <div className="space-y-2 px-4 pt-4">
        <div className="h-3.5 w-24 animate-pulse rounded-full bg-muted" />
        <div className="h-3.5 w-2/3 animate-pulse rounded-full bg-muted" />
      </div>
    </div>
  );
}
