import type { User } from "@supabase/supabase-js";
import { describe, expect, it } from "vitest";

import { toSessionUser } from "./auth";

const user = (overrides: Partial<User>): User =>
  ({ id: "u1", email: "taro@example.com", user_metadata: {}, ...overrides }) as User;

describe("toSessionUser", () => {
  it("Google の名前とアイコンを使う", () => {
    const result = toSessionUser(
      user({ user_metadata: { full_name: "山田太郎", avatar_url: "https://example.com/a.png" } }),
    );

    expect(result).toEqual({
      id: "u1",
      email: "taro@example.com",
      display_name: "山田太郎",
      avatar_url: "https://example.com/a.png",
    });
  });

  it("full_name がなければ name、アイコンは picture を使う", () => {
    const result = toSessionUser(user({ user_metadata: { name: "taro", picture: "https://example.com/p.png" } }));

    expect(result.display_name).toBe("taro");
    expect(result.avatar_url).toBe("https://example.com/p.png");
  });

  it("名前がなければメールアドレスの @ より前を使い、アイコンは null", () => {
    const result = toSessionUser(user({}));

    expect(result.display_name).toBe("taro");
    expect(result.avatar_url).toBeNull();
  });
});
