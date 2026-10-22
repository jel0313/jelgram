"use client";

import { HeartIcon, Loader2Icon, SparklesIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { Logo } from "@/components/common/logo";
import { Button } from "@/components/ui/button";

/** ログイン画面(未ログインのときはこの画面だけを表示する) */
export default function LoginPage() {
  const { user, loading, signIn } = useAuth();
  const router = useRouter();
  const [signingIn, setSigningIn] = useState(false);

  // ログイン済みならタイムラインへ
  useEffect(() => {
    if (!loading && user) router.replace("/");
  }, [loading, user, router]);

  const handleSignIn = async () => {
    setSigningIn(true);
    try {
      // Google のログイン画面へ移る(終わるとタイムラインに戻ってくる)
      await signIn();
    } catch {
      toast.error("ログインに失敗しました。もう一度お試しください");
      setSigningIn(false);
    }
  };

  return (
    <main className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-background px-4 py-10">
      {/* 背景のぼんやりした色(ブランドの 3 色) */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute -top-32 -left-24 size-[28rem] rounded-full bg-(--brand-from) opacity-25 blur-3xl" />
        <div className="absolute top-1/3 -right-32 size-[30rem] rounded-full bg-(--brand-via) opacity-20 blur-3xl" />
        <div className="absolute -bottom-40 left-1/4 size-[26rem] rounded-full bg-(--brand-to) opacity-20 blur-3xl" />
      </div>

      <div className="relative flex w-full max-w-4xl items-center justify-center gap-16">
        <Showcase />

        <div className="w-full max-w-sm rounded-[2rem] border border-white/60 bg-card/80 px-8 py-10 text-center shadow-[0_20px_60px_-20px_rgb(0_0_0/0.25)] backdrop-blur-xl">
          <Logo className="text-6xl" />
          <p className="mt-4 text-lg font-semibold">AI が常駐する SNS</p>
          <p className="mt-1.5 text-sm text-muted-foreground">投稿にツッコむ AI と、いつでも話せる</p>

          <Button
            size="lg"
            className="mt-8 h-12 w-full gap-3 rounded-full text-[15px] font-semibold shadow-lg shadow-black/10"
            onClick={handleSignIn}
            disabled={signingIn || loading}
          >
            {signingIn ? (
              <Loader2Icon className="animate-spin" />
            ) : (
              <span className="flex size-6 items-center justify-center rounded-full bg-white">
                <GoogleIcon />
              </span>
            )}
            Google でログイン
          </Button>
          <p className="mt-5 text-xs leading-relaxed text-muted-foreground">
            ログインすると、タイムラインと AI チャットを使えます
          </p>
        </div>
      </div>
    </main>
  );
}

/** PC だけ:左に出す、投稿と AI の会話の見本(飾り) */
function Showcase() {
  return (
    <div aria-hidden className="relative hidden h-[30rem] w-80 shrink-0 lg:block">
      {/* 後ろの投稿 */}
      <div className="absolute top-6 left-0 w-60 -rotate-6 overflow-hidden rounded-3xl border bg-card shadow-xl">
        <div className="aspect-[4/5] bg-linear-to-br from-amber-200 via-rose-300 to-violet-400" />
      </div>
      {/* いいねの数 */}
      <div className="absolute top-8 right-2 z-10 flex items-center gap-1.5 rounded-full bg-card px-3 py-1.5 text-xs font-semibold shadow-lg">
        <HeartIcon className="size-4 fill-(--like) text-(--like)" />
        128
      </div>
      {/* 手前の投稿 */}
      <div className="absolute top-16 right-0 w-60 rotate-3 overflow-hidden rounded-3xl border bg-card shadow-2xl">
        <div className="flex items-center gap-2 px-3 py-2.5">
          <span className="bg-brand size-7 rounded-full p-[2px]">
            <span className="block size-full rounded-full border-2 border-card bg-linear-to-br from-sky-200 to-indigo-300" />
          </span>
          <span className="h-2 w-16 rounded-full bg-muted" />
        </div>
        <div className="aspect-square bg-linear-to-br from-sky-200 via-indigo-200 to-fuchsia-300" />
        <div className="space-y-1.5 p-3">
          <span className="block h-2 w-3/4 rounded-full bg-muted" />
          <span className="block h-2 w-1/2 rounded-full bg-muted" />
        </div>
      </div>
      {/* AI の吹き出し */}
      <div className="absolute bottom-6 -left-4 flex max-w-64 items-end gap-2">
        <span className="bg-brand flex size-8 shrink-0 items-center justify-center rounded-full text-white shadow-lg">
          <SparklesIcon className="size-4" />
        </span>
        <p className="rounded-3xl rounded-bl-md border bg-card px-4 py-2.5 text-sm shadow-xl">
          その写真、もう少し寄ったほうが映えるよ
        </p>
      </div>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="size-4">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.1A6.6 6.6 0 0 1 5.5 12c0-.73.13-1.44.34-2.1V7.06H2.18A11 11 0 0 0 1 12c0 1.77.43 3.45 1.18 4.94l3.66-2.84z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"
      />
    </svg>
  );
}
