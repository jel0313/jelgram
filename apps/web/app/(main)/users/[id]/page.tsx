"use client";

import { CalendarIcon, CameraIcon, Grid3X3Icon, HeartIcon, UserXIcon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { PhaseBadge } from "@/components/common/phase-badge";
import { UserAvatar } from "@/components/common/user-avatar";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePostList } from "@/hooks/use-post-list";
import { ApiError, errorMessage } from "@/lib/api/errors";
import type { Post, UserProfile } from "@/lib/api/types";
import { getUser, getUserPosts } from "@/lib/api/users";
import { formatYearMonth } from "@/lib/format";

/** ユーザーページ(その人のプロフィールと、投稿のグリッド。4次) */
export default function UserPage() {
  const { id } = useParams<{ id: string }>();
  const { user: me } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileError, setProfileError] = useState<{ message: string; notFound: boolean } | null>(null);

  const fetchUserPosts = useCallback(() => getUserPosts(id), [id]);
  const { posts, loading, error, reload } = usePostList(fetchUserPosts);

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

  const totalLikes = posts.reduce((sum, post) => sum + post.like_count, 0);

  return (
    <>
      <PageHeader title={profile?.display_name ?? "ユーザー"} back>
        <PhaseBadge phase="4次" />
      </PageHeader>

      <section className="px-4 pt-4 pb-6 md:px-0 md:pt-6">
        {profile ? (
          <div className="flex items-center gap-6 md:gap-10">
            <UserAvatar
              name={profile.display_name}
              src={profile.avatar_url}
              ring
              className="size-22 text-3xl md:size-36 md:text-5xl"
            />
            <div className="min-w-0 flex-1 space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="truncate text-xl font-semibold">{profile.display_name}</h2>
                {me?.id === profile.id && (
                  <Button asChild variant="secondary" className="h-8 rounded-lg px-4 font-semibold">
                    <Link href="/settings/profile">プロフィールを編集</Link>
                  </Button>
                )}
              </div>
              <dl className="flex gap-6 text-sm">
                <Stat label="投稿" value={profile.post_count} />
                <Stat label="いいね" value={loading ? null : totalLikes} />
              </dl>
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <CalendarIcon className="size-3.5" />
                {formatYearMonth(profile.created_at)}から利用
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-6 md:gap-10">
            <Skeleton className="size-22 rounded-full md:size-36" />
            <div className="flex-1 space-y-3">
              <Skeleton className="h-6 w-40" />
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-32" />
            </div>
          </div>
        )}
      </section>

      <div className="flex justify-center border-t border-border/70">
        <span className="-mt-px flex items-center gap-1.5 border-t border-foreground py-3 text-xs font-semibold tracking-widest">
          <Grid3X3Icon className="size-3.5" />
          投稿
        </span>
      </div>

      {loading ? (
        <div className="grid grid-cols-3 gap-0.5 md:gap-1">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="aspect-square rounded-none md:rounded-md" />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : posts.length === 0 ? (
        <EmptyState icon={<CameraIcon />} title="まだ投稿がありません" />
      ) : (
        <div className="grid grid-cols-3 gap-0.5 md:gap-1">
          {posts.map((post) => (
            <PostTile key={post.id} post={post} />
          ))}
        </div>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="flex gap-1">
      <dt className="order-last text-muted-foreground">{label}</dt>
      <dd className="font-semibold tabular-nums">{value === null ? "–" : value.toLocaleString()}</dd>
    </div>
  );
}

/** グリッドの 1 マス。画像があれば画像、なければ本文をカードにして出す。押すと投稿詳細へ */
function PostTile({ post }: { post: Post }) {
  return (
    <Link
      href={`/posts/${post.id}`}
      className="group relative block aspect-square overflow-hidden bg-muted md:rounded-md"
      aria-label={post.content}
    >
      {post.image_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={post.image_url} alt="" className="size-full object-cover" />
      ) : (
        <div className="flex size-full items-center justify-center bg-linear-to-br from-orange-50 via-pink-50 to-violet-100 p-3">
          <p className="line-clamp-5 text-center text-xs leading-relaxed font-medium text-foreground/80 md:text-sm">
            {post.content}
          </p>
        </div>
      )}
      <span className="absolute inset-0 flex items-center justify-center gap-1.5 bg-black/35 font-semibold text-white opacity-0 transition-opacity group-hover:opacity-100">
        <HeartIcon className="size-5 fill-current" />
        {post.like_count}
      </span>
    </Link>
  );
}
