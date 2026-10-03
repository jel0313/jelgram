// ユーザー・プロフィール(4次)。いまはダミー実装(画面接続で、本物の API 呼び出しに置き換える)。

import { ApiError } from "./errors";
import { MOCK_ME, mockPosts, mockUsers, shouldMockFail, sleep } from "./mock-data";
import type { Post, ProfileUpdate, UserProfile } from "./types";

/** ユーザー 1 人(ユーザーページの上部) */
export async function getUser(userId: string): Promise<UserProfile> {
  await sleep(400);
  if (shouldMockFail()) throw new ApiError(500, "ユーザーを読み込めませんでした");
  const user = mockUsers.get(userId);
  if (!user) throw new ApiError(404, "ユーザーが見つかりません");
  return {
    id: user.id,
    display_name: user.display_name,
    avatar_url: user.avatar_url,
    created_at: user.created_at,
    post_count: mockPosts.filter((p) => p.author.id === userId).length,
  };
}

/** そのユーザーの投稿(新しい順) */
export async function getUserPosts(userId: string): Promise<Post[]> {
  await sleep(500);
  return structuredClone(mockPosts.filter((p) => p.author.id === userId));
}

/** 自分のプロフィールを変更する */
export async function updateMyProfile(body: ProfileUpdate): Promise<UserProfile> {
  await sleep(500);
  // ダミー:投稿の投稿者(MOCK_ME)も同じものなので、タイムラインの表示名も変わる
  MOCK_ME.display_name = body.display_name.trim();
  MOCK_ME.avatar_url = body.avatar_url;
  const user = mockUsers.get(MOCK_ME.id)!;
  mockUsers.set(MOCK_ME.id, { ...user, display_name: MOCK_ME.display_name, avatar_url: MOCK_ME.avatar_url });
  return getUser(MOCK_ME.id);
}
