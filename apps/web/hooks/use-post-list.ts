"use client";

import { useCallback, useEffect, useState } from "react";

import type { PostCardHandlers } from "@/components/posts/post-card";
import { errorMessage } from "@/lib/api/errors";
import type { Post } from "@/lib/api/types";

/**
 * 投稿の一覧の読み込みと、投稿・いいね・編集・削除の反映(タイムライン・ユーザーページで使う)。
 * fetcher は useCallback などで同じ関数を渡す(変わるたびに読み直す)。
 */
export function usePostList(fetcher: () => Promise<Post[]>) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPosts = useCallback(
    () =>
      fetcher()
        .then((result) => {
          setPosts(result);
          setError(null);
        })
        .catch((e) => setError(errorMessage(e)))
        .finally(() => setLoading(false)),
    [fetcher],
  );

  useEffect(() => {
    void fetchPosts();
  }, [fetchPosts]);

  /** 再読み込み(エラーのときのボタン) */
  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    void fetchPosts();
  }, [fetchPosts]);

  /** 投稿したものを先頭に足す */
  const addPost = useCallback((post: Post) => setPosts((prev) => [post, ...prev]), []);

  const handlers: PostCardHandlers = {
    onLikeChange: (postId, likeCount, likedByMe) =>
      setPosts((prev) =>
        prev.map((p) => (p.id === postId ? { ...p, like_count: likeCount, liked_by_me: likedByMe } : p)),
      ),
    onUpdated: (post) => setPosts((prev) => prev.map((p) => (p.id === post.id ? post : p))),
    onDeleted: (postId) => setPosts((prev) => prev.filter((p) => p.id !== postId)),
  };

  return { posts, loading, error, reload, addPost, handlers };
}
