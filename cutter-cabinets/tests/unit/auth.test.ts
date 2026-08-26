import { describe, expect, it } from "vitest";

import { hashPassword, verifyPassword } from "@/lib/auth/password";

describe("password hashing", () => {
  it("verifies the original password and rejects a different one", () => {
    const hash = hashPassword("correct-password");

    expect(hash).not.toContain("correct-password");
    expect(verifyPassword("correct-password", hash)).toBe(true);
    expect(verifyPassword("wrong-password", hash)).toBe(false);
  });
});
