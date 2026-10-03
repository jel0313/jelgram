// ログイン・ログアウト。いまはダミー実装(画面接続 5.1 で Supabase Auth に置き換える)。
// ダミーでは、ログイン状態をブラウザの localStorage に保存している。

import { MOCK_ME, sleep } from "./api/mock-data";

/** ログイン中のユーザー(画面の表示用) */
export type SessionUser = {
  id: string;
  email: string | null;
  display_name: string;
  avatar_url: string | null;
};

const STORAGE_KEY = "jelgram-mock-session";

/** 今のログイン状態。ログインしていなければ null */
export async function getSessionUser(): Promise<SessionUser | null> {
  const saved = window.localStorage.getItem(STORAGE_KEY);
  return saved ? (JSON.parse(saved) as SessionUser) : null;
}

/** Google でログインする */
export async function signInWithGoogle(): Promise<SessionUser> {
  await sleep(700);
  const user: SessionUser = { ...MOCK_ME, email: "makino_test@example.com" };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
  return user;
}

/** ログアウトする */
export async function signOut(): Promise<void> {
  await sleep(200);
  window.localStorage.removeItem(STORAGE_KEY);
}

/** ログイン中のユーザーの表示を更新する(プロフィールを変えたとき) */
export async function saveSessionUser(user: SessionUser): Promise<void> {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
}
