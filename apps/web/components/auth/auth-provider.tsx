"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { getSessionUser, onAuthChange, signInWithGoogle, signOut, type SessionUser } from "@/lib/auth";

type AuthState = {
  /** ログイン中のユーザー。未ログインなら null */
  user: SessionUser | null;
  /** ログイン状態を確認中か(最初の表示のとき) */
  loading: boolean;
  /** Google のログイン画面へ移る */
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  /** 表示名・アイコンを変えたときに、画面の表示を更新する(4次) */
  updateUser: (changes: Pick<SessionUser, "display_name" | "avatar_url">) => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 最初の表示:今のログイン状態を読む(Google から戻ってきた直後は、ここでログインが完了する)
    getSessionUser()
      .then(setUser)
      .finally(() => setLoading(false));
    // その後の変化(ログアウト・別タブでのログインなど)を反映する
    return onAuthChange(setUser);
  }, []);

  const handleSignOut = useCallback(async () => {
    await signOut();
    setUser(null);
  }, []);

  const updateUser = useCallback((changes: Pick<SessionUser, "display_name" | "avatar_url">) => {
    setUser((prev) => (prev ? { ...prev, ...changes } : prev));
  }, []);

  return (
    <AuthContext value={{ user, loading, signIn: signInWithGoogle, signOut: handleSignOut, updateUser }}>
      {children}
    </AuthContext>
  );
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (!state) throw new Error("useAuth は AuthProvider の中で使う");
  return state;
}
