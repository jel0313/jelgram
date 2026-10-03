"use client";

import { CalendarIcon, MessageSquareTextIcon, PencilIcon, UserXIcon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { PhaseBadge } from "@/components/common/phase-badge";
import { UserAvatar } from "@/components/common/user-avatar";
import { PageHeader } from "@/components/layout/page-header";
import { PostCard, PostCardSkeleton } from "@/components/posts/post-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePostList } from "@/hooks/use-post-list";
import { ApiError, errorMessage } from "@/lib/api/errors";
import type { UserProfile } from "@/lib/api/types";
import { getUser, getUserPosts } from "@/lib/api/users";
import { formatYearMonth } from "@/lib/format";

/** ユーザーページ(その人のプロフィールと投稿の一覧。4次) */
export default function UserPage() {
  const { id } = useParams<{ id: string }>();
  const { user: me } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileError, setProfileError] = useState<{ message: string; notFound: boolean } | null>(null);

  const fetchUserPosts = useCallback(() => getUserPosts(id), [id]);
  const { posts, loading, error, reload, handlers } = usePostList(fetchUserPosts);

  useEffect(() => {
    getUser(id)
      .then(setProfile)
      .catch((e) =>
        setProfileError({ message: errorMessage(e), notFound: e instanceof ApiError && e.status === 404 }),
      );
  }, [id]);

  if (profileError?.notFound) {
    return (
      <>
        <PageHeader title="ユーザー" back />
        <EmptyState icon={<UserXIcon />} title="ユーザーが見つかりません" />
      </>
    );
  }
  if (profileError) {
    return (
      <>
        <PageHeader title="ユーザー" back />
        <ErrorState message={profileError.message} onRetry={() => window.location.reload()} />
      </>
    );
  }

  return (
    <>
      <PageHeader title={profile?.display_name ?? "ユーザー"} back>
        <PhaseBadge phase="4次" />
      </PageHeader>

      <section className="space-y-4 border-b px-4 py-6">
        {profile ? (
          <>
            <div className="flex items-start justify-between gap-4">
              <UserAvatar name={profile.display_name} src={profile.avatar_url} className="size-20 text-2xl" />
              {me?.id === profile.id && (
                <Button asChild variant="outline" className="rounded-full">
                  <Link href="/settings/profile">
                    <PencilIcon />
                    プロフィールを編集
                  </Link>
                </Button>
              )}
            </div>
            <div className="space-y-1">
              <p className="text-xl font-bold">{profile.display_name}</p>
              <p className="flex items-center gap-4 text-sm text-muted-foreground">
                <span className="flex items-center gap-1">
                  <CalendarIcon className="size-4" />
                  {formatYearMonth(profile.created_at)}から利用
                </span>
                <span>
                  <span className="font-semibold text-foreground">{profile.post_count}</span> 件の投稿
                </span>
              </p>
            </div>
          </>
        ) : (
          <>
            <Skeleton className="size-20 rounded-full" />
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-4 w-56" />
          </>
        )}
      </section>

      {loading ? (
        Array.from({ length: 3 }, (_, i) => <PostCardSkeleton key={i} />)
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : posts.length === 0 ? (
        <EmptyState icon={<MessageSquareTextIcon />} title="まだ投稿がありません" />
      ) : (
        posts.map((post) => <PostCard key={post.id} post={post} {...handlers} />)
      )}
    </>
  );
}
