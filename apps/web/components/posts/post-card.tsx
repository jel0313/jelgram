"use client";

import { BotIcon } from "lucide-react";
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
  /** 投稿詳細画面で使う(文字を大きく・日時をそのまま表示) */
  detail?: boolean;
};

/** 投稿 1 件 */
export function PostCard({ post, detail = false, onLikeChange, onUpdated, onDeleted }: Props) {
  const { askAbout } = useChat();
  const { user } = useAuth();
  const isMine = user?.id === post.author.id;
  const userHref = `/users/${post.author.id}`;

  return (
    <article className="flex gap-3 border-b px-4 py-4">
      <Link href={userHref} className="shrink-0" aria-label={`${post.author.display_name} のページ`}>
        <UserAvatar name={post.author.display_name} src={post.author.avatar_url} size="lg" />
      </Link>
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex items-center gap-2 text-sm">
          <Link href={userHref} className="truncate font-semibold hover:underline">
            {post.author.display_name}
          </Link>
          {detail ? (
            <time dateTime={post.created_at} className="shrink-0 text-muted-foreground">
              {formatDateTime(post.created_at)}
            </time>
          ) : (
            <Link href={`/posts/${post.id}`} className="shrink-0 text-muted-foreground hover:underline">
              <time dateTime={post.created_at}>{formatRelativeTime(post.created_at)}</time>
            </Link>
          )}
          {isMine && (
            <div className="ml-auto -my-1">
              <PostMenu post={post} onUpdated={onUpdated} onDeleted={onDeleted} />
            </div>
          )}
        </div>
        {detail ? (
          <p className="text-lg leading-relaxed whitespace-pre-wrap">{post.content}</p>
        ) : (
          <Link href={`/posts/${post.id}`} className="block">
            <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{post.content}</p>
          </Link>
        )}
        {post.image_url && (
          <ImageViewer
            src={post.image_url}
            className={cn("w-full rounded-xl border object-cover", detail ? "max-h-128" : "max-h-96")}
          />
        )}
        <div className="-ml-2 flex items-center gap-4">
          <LikeButton post={post} onChange={onLikeChange} />
          <button
            type="button"
            onClick={() => askAbout(post)}
            className="flex items-center gap-1.5 rounded-full px-2 py-1 text-sm text-muted-foreground transition-colors hover:text-violet-600"
          >
            <BotIcon className="size-4.5" />
            この投稿について
          </button>
        </div>
      </div>
    </article>
  );
}

/** 読み込み中の投稿の形 */
export function PostCardSkeleton() {
  return (
    <div className="flex gap-3 border-b px-4 py-4">
      <div className="size-10 shrink-0 animate-pulse rounded-full bg-muted" />
      <div className="flex-1 space-y-2">
        <div className="h-4 w-32 animate-pulse rounded bg-muted" />
        <div className="h-4 w-full animate-pulse rounded bg-muted" />
        <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
      </div>
    </div>
  );
}
