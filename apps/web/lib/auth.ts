// ログイン・ログアウト(Supabase Auth の Google ログイン。WBS 5.1)

import type { User } from "@supabase/supabase-js";

import { getSupabase } from "./supabase";

/** ログイン中のユーザー(画面の表示用) */
export type SessionUser = {
  id: string;
  email: string | null;
  display_name: string;
  avatar_url: string | null;
};

/**
 * Supabase のユーザーを、画面で使う形にする。
 * 表示名・アイコンは Google アカウントの情報(profiles を作るトリガーと同じ決め方)。
 */
export function toSessionUser(user: User): SessionUser {
  const meta = user.user_metadata ?? {};
  const email = user.email ?? null;
  return {
    id: user.id,
    email,
    display_name: meta.full_name || meta.name || email?.split("@")[0] || "ユーザー",
    avatar_url: meta.avatar_url || meta.picture || null,
  };
}

/** 今のログイン状態。ログインしていなければ null */
export async function getSessionUser(): Promise<SessionUser | null> {
  const { data } = await getSupabase().auth.getSession();
  return data.session ? toSessionUser(data.session.user) : null;
}

/** ログイン状態が変わったら(ログイン・ログアウト・トークンの更新)知らせる。戻り値は購読をやめる関数 */
export function onAuthChange(callback: (user: SessionUser | null) => void): () => void {
  const { data } = getSupabase().auth.onAuthStateChange((_event, session) => {
    callback(session ? toSessionUser(session.user) : null);
  });
  return () => data.subscription.unsubscribe();
}

/**
 * Google でログインする。Google のログイン画面へ移り、終わるとタイムライン(/)に戻ってくる。
 */
export async function signInWithGoogle(): Promise<void> {
  const { error } = await getSupabase().auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: `${window.location.origin}/` },
  });
  if (error) throw error;
}

/** ログアウトする */
export async function signOut(): Promise<void> {
  const { error } = await getSupabase().auth.signOut();
  if (error) throw error;
}

/** API に付けるアクセストークン(JWT)。ログインしていなければ null */
export async function getAccessToken(): Promise<string | null> {
  const { data } = await getSupabase().auth.getSession();
  return data.session?.access_token ?? null;
}
