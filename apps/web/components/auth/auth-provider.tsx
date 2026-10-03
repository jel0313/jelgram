"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { getSessionUser, saveSessionUser, signInWithGoogle, signOut, type SessionUser } from "@/lib/auth";

type AuthState = {
  /** ログイン中のユーザー。未ログインなら null */
  user: SessionUser | null;
  /** ログイン状態を確認中か(最初の表示のとき) */
  loading: boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  /** 表示名・アイコンを変えたときに、画面の表示を更新する */
  updateUser: (changes: Pick<SessionUser, "display_name" | "avatar_url">) => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSessionUser()
      .then(setUser)
      .finally(() => setLoading(false));
  }, []);

  const signIn = useCallback(async () => {
    setUser(await signInWithGoogle());
  }, []);

  const handleSignOut = useCallback(async () => {
    await signOut();
    setUser(null);
  }, []);

  const updateUser = useCallback((changes: Pick<SessionUser, "display_name" | "avatar_url">) => {
    setUser((prev) => {
      if (!prev) return prev;
      const next = { ...prev, ...changes };
      void saveSessionUser(next);
      return next;
    });
  }, []);

  return (
    <AuthContext value={{ user, loading, signIn, signOut: handleSignOut, updateUser }}>{children}</AuthContext>
  );
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (!state) throw new Error("useAuth は AuthProvider の中で使う");
  return state;
}
