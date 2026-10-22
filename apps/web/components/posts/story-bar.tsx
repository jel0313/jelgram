"use client";

import { SparklesIcon } from "lucide-react";
import Link from "next/link";

import { useChat } from "@/components/chat/chat-provider";
import { UserAvatar } from "@/components/common/user-avatar";
import type { Author, Post } from "@/lib/api/types";

/** 横に並べる人数の上限 */
const MAX_AUTHORS = 12;

/**
 * タイムラインの上の、インスタのストーリー風のアイコンの列。
 * 先頭は AI(押すとチャットを開く)、その後ろに最近投稿した人(押すとユーザーページ)。
 */
export function StoryBar({ posts }: { posts: Post[] }) {
  const { openChat } = useChat();

  // 新しい投稿の順に、投稿者を重ならないように集める
  const authors = new Map<string, Author>();
  for (const post of posts) {
    if (authors.size >= MAX_AUTHORS) break;
    if (!authors.has(post.author.id)) authors.set(post.author.id, post.author);
  }

  return (
    <div className="scrollbar-none flex gap-4 overflow-x-auto border-b border-border/60 px-4 py-4 md:mb-6 md:rounded-3xl md:border md:border-border/70 md:bg-card md:px-5 md:shadow-[0_2px_16px_-8px_rgb(0_0_0/0.08)]">
      <button type="button" onClick={openChat} className="group flex w-16 shrink-0 flex-col items-center gap-1.5">
        <span className="bg-brand flex size-16 items-center justify-center rounded-full p-[2.5px] transition-transform group-active:scale-95">
          <span className="flex size-full items-center justify-center rounded-full bg-card">
            <span className="bg-brand flex size-[52px] items-center justify-center rounded-full text-white">
              <SparklesIcon className="size-6" />
            </span>
          </span>
        </span>
        <span className="w-full truncate text-center text-xs font-medium">AI</span>
      </button>
      {[...authors.values()].map((author) => (
        <Link
          key={author.id}
          href={`/users/${author.id}`}
          className="group flex w-16 shrink-0 flex-col items-center gap-1.5"
        >
          <UserAvatar
            name={author.display_name}
            src={author.avatar_url}
            ring
            className="size-16 text-lg transition-transform group-active:scale-95"
          />
          <span className="w-full truncate text-center text-xs">{author.display_name}</span>
        </Link>
      ))}
    </div>
  );
}

/** 読み込み中のストーリーの列 */
export function StoryBarSkeleton() {
  return (
    <div className="flex gap-4 overflow-hidden border-b border-border/60 px-4 py-4 md:mb-6 md:rounded-3xl md:border md:border-border/70 md:bg-card md:px-5">
      {Array.from({ length: 5 }, (_, i) => (
        <div key={i} className="flex w-16 shrink-0 flex-col items-center gap-1.5">
          <div className="size-16 animate-pulse rounded-full bg-muted" />
          <div className="h-3 w-10 animate-pulse rounded-full bg-muted" />
        </div>
      ))}
    </div>
  );
}
