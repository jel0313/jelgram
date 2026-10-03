// 投稿・いいね。いまはダミー実装(画面接続で、本物の API 呼び出しに置き換える)。

import { ApiError } from "./errors";
import { MOCK_ME, mockOthersLikeCount, mockPosts, newId, shouldMockFail, sleep } from "./mock-data";
import type { LikeResult, Post, PostCreate, PostUpdate } from "./types";

/** タイムライン(新しい順) */
export async function getTimeline(): Promise<Post[]> {
  await sleep(600);
  if (shouldMockFail()) throw new ApiError(500, "タイムラインを読み込めませんでした");
  return structuredClone(mockPosts);
}

/** 投稿する */
export async function createPost(body: PostCreate): Promise<Post> {
  await sleep(500);
  const post: Post = {
    id: newId(),
    content: body.content.trim(),
    image_url: body.image_url,
    created_at: new Date().toISOString(),
    author: MOCK_ME,
    like_count: 0,
    liked_by_me: false,
  };
  mockPosts.unshift(post);
  mockOthersLikeCount.set(post.id, 0);
  return structuredClone(post);
}

/** いいねする(いいね済みなら何もしない) */
export async function likePost(postId: number): Promise<LikeResult> {
  return setLiked(postId, true);
}

/** いいねを取り消す(いいねしていなければ何もしない) */
export async function unlikePost(postId: number): Promise<LikeResult> {
  return setLiked(postId, false);
}

async function setLiked(postId: number, liked: boolean): Promise<LikeResult> {
  await sleep(250);
  const post = mockPosts.find((p) => p.id === postId);
  if (!post) throw new ApiError(404, "投稿が見つかりません");
  post.liked_by_me = liked;
  post.like_count = (mockOthersLikeCount.get(postId) ?? 0) + (liked ? 1 : 0);
  return { post_id: postId, like_count: post.like_count, liked_by_me: post.liked_by_me };
}

/** 投稿 1 件(投稿詳細画面) */
export async function getPost(postId: number): Promise<Post> {
  await sleep(400);
  if (shouldMockFail()) throw new ApiError(500, "投稿を読み込めませんでした");
  const post = mockPosts.find((p) => p.id === postId);
  if (!post) throw new ApiError(404, "投稿が見つかりません");
  return structuredClone(post);
}

/** 投稿を編集する(自分の投稿だけ。2次) */
export async function updatePost(postId: number, body: PostUpdate): Promise<Post> {
  await sleep(400);
  const post = mockPosts.find((p) => p.id === postId);
  if (!post) throw new ApiError(404, "投稿が見つかりません");
  if (post.author.id !== MOCK_ME.id) throw new ApiError(403, "自分の投稿だけ編集できます");
  post.content = body.content.trim();
  return structuredClone(post);
}

/** 投稿を削除する(自分の投稿だけ。2次) */
export async function deletePost(postId: number): Promise<void> {
  await sleep(400);
  const index = mockPosts.findIndex((p) => p.id === postId);
  if (index === -1) throw new ApiError(404, "投稿が見つかりません");
  if (mockPosts[index].author.id !== MOCK_ME.id) throw new ApiError(403, "自分の投稿だけ削除できます");
  mockPosts.splice(index, 1);
}
