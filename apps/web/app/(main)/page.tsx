"use client";

import { MessageSquareTextIcon } from "lucide-react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { PageHeader } from "@/components/layout/page-header";
import { PostCard, PostCardSkeleton } from "@/components/posts/post-card";
import { PostComposer } from "@/components/posts/post-composer";
import { usePostList } from "@/hooks/use-post-list";
import { getTimeline } from "@/lib/api/posts";

/** タイムライン(ホーム) */
export default function TimelinePage() {
  const { posts, loading, error, reload, addPost, handlers } = usePostList(getTimeline);

  return (
    <>
      <PageHeader title="ホーム" />
      <PostComposer onCreated={addPost} />
      {loading ? (
        Array.from({ length: 4 }, (_, i) => <PostCardSkeleton key={i} />)
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : posts.length === 0 ? (
        <EmptyState
          icon={<MessageSquareTextIcon />}
          title="まだ投稿がありません"
          description="最初の投稿をしてみよう"
        />
      ) : (
        posts.map((post) => <PostCard key={post.id} post={post} {...handlers} />)
      )}
    </>
  );
}
