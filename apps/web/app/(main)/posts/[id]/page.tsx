"use client";

import { FileQuestionIcon } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { PageHeader } from "@/components/layout/page-header";
import { PostCard, PostCardSkeleton } from "@/components/posts/post-card";
import { ApiError, errorMessage } from "@/lib/api/errors";
import { getPost } from "@/lib/api/posts";
import type { Post } from "@/lib/api/types";

/** 投稿詳細(/posts/12 のように、投稿 1 件を表示する) */
export default function PostDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [post, setPost] = useState<Post | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; notFound: boolean } | null>(null);

  const fetchPost = useCallback(
    () =>
      getPost(Number(id))
        .then((result) => {
          setPost(result);
          setError(null);
        })
        .catch((e) =>
          setError({ message: errorMessage(e), notFound: e instanceof ApiError && e.status === 404 }),
        )
        .finally(() => setLoading(false)),
    [id],
  );

  useEffect(() => {
    void fetchPost();
  }, [fetchPost]);

  return (
    <>
      <PageHeader title="投稿" back />
      {loading ? (
        <PostCardSkeleton />
      ) : error?.notFound ? (
        <EmptyState
          icon={<FileQuestionIcon />}
          title="投稿が見つかりません"
          description="削除されたか、URL が間違っている可能性があります"
        />
      ) : error || !post ? (
        <ErrorState
          message={error?.message ?? ""}
          onRetry={() => {
            setLoading(true);
            void fetchPost();
          }}
        />
      ) : (
        <PostCard
          post={post}
          detail
          onLikeChange={(_, likeCount, likedByMe) =>
            setPost({ ...post, like_count: likeCount, liked_by_me: likedByMe })
          }
          onUpdated={setPost}
          onDeleted={() => router.replace("/")}
        />
      )}
    </>
  );
}
