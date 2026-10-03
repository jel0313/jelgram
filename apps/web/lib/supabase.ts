import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

/** ブラウザで使う Supabase のクライアント(1 つだけ作って使い回す) */
export function getSupabase(): SupabaseClient {
  if (!client) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    if (!url || !key) {
      throw new Error("NEXT_PUBLIC_SUPABASE_URL と NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY を .env.local に設定してください");
    }
    client = createClient(url, key, {
      // ログイン後に URL へ付く「?code=...」を、トークンに交換する方式(PKCE)
      auth: { flowType: "pkce" },
    });
  }
  return client;
}
