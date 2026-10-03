"use client";

import { BotIcon, Loader2Icon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { Logo } from "@/components/common/logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

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
      await signIn();
      router.replace("/");
    } catch {
      toast.error("ログインに失敗しました。もう一度お試しください");
      setSigningIn(false);
    }
  };

  return (
    <main className="flex min-h-dvh items-center justify-center bg-linear-to-br from-violet-50 via-background to-pink-50 px-4 dark:from-violet-950/30 dark:to-pink-950/30">
      <Card className="w-full max-w-sm">
        <CardContent className="flex flex-col items-center gap-6 py-6 text-center">
          <Logo className="text-4xl" />
          <div className="space-y-2">
            <p className="text-lg font-semibold">AI が常駐する SNS</p>
            <p className="flex items-center justify-center gap-1.5 text-sm text-muted-foreground">
              <BotIcon className="size-4 text-violet-500" />
              投稿にツッコむ AI と、いつでも話せる
            </p>
          </div>
          <Button
            size="lg"
            variant="outline"
            className="w-full gap-2"
            onClick={handleSignIn}
            disabled={signingIn || loading}
          >
            {signingIn ? <Loader2Icon className="animate-spin" /> : <GoogleIcon />}
            Google でログイン
          </Button>
          <p className="text-xs text-muted-foreground">ログインすると、タイムラインと AI チャットを使えます</p>
        </CardContent>
      </Card>
    </main>
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
