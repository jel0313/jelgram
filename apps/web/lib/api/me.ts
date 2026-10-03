// ログイン中のユーザー(API の GET /me。トークンが API に届くかの確認用)

import { apiFetch } from "./client";

export type Me = {
  id: string;
  email: string | null;
};

/** トークンで特定したユーザーを返す(GET /me) */
export function getMe(): Promise<Me> {
  return apiFetch<Me>("/me");
}
