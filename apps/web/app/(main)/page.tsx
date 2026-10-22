"use client";

import { CameraIcon } from "lucide-react";
import { useEffect } from "react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { COMPOSER_INPUT_ID } from "@/components/layout/app-sidebar";
import { PostCard, PostCardSkeleton } from "@/components/posts/post-card";
import { PostComposer } from "@/components/posts/post-composer";
import { StoryBar, StoryBarSkeleton } from "@/components/posts/story-bar";
import { usePostList } from "@/hooks/use-post-list";
import { getTimeline } from "@/lib/api/posts";

/** タイムライン(ホーム) */
export default function TimelinePage() {
  const { posts, loading, error, reload, addPost, handlers } = usePostList(getTimeline);

  // ほかの画面で「投稿する」を押して来たとき(/?compose=1)は、投稿フォームにフォーカスする
  useEffect(() => {
    if (!new URLSearchParams(window.location.search).has("compose")) return;
    document.getElementById(COMPOSER_INPUT_ID)?.focus();
    window.history.replaceState(null, "", "/");
  }, []);

  return (
    <div className="md:pt-8">
      <h1 className="sr-only">ホーム</h1>
      {loading ? <StoryBarSkeleton /> : !error && posts.length > 0 && <StoryBar posts={posts} />}
      <PostComposer onCreated={addPost} />
      {loading ? (
        Array.from({ length: 3 }, (_, i) => <PostCardSkeleton key={i} />)
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : posts.length === 0 ? (
        <EmptyState icon={<CameraIcon />} title="まだ投稿がありません" description="最初の投稿をしてみよう" />
      ) : (
        posts.map((post) => <PostCard key={post.id} post={post} {...handlers} />)
      )}
    </div>
  );
}
