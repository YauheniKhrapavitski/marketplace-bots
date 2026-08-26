import { cookies } from "next/headers";
import { createHmac, timingSafeEqual } from "node:crypto";

const COOKIE_NAME = "cutter_session";

export type SessionUser = {
  id: string;
  role: "CUTTER" | "ADMIN";
  cutterId?: string;
  displayName: string;
};

export async function readSessionUser(): Promise<SessionUser | null> {
  const cookieStore = await cookies();
  const raw = cookieStore.get(COOKIE_NAME)?.value;
  if (!raw) {
    return null;
  }

  try {
    const [payload, signature] = raw.split(".");
    if (!payload || !signature || !verifySignature(payload, signature)) {
      return null;
    }

    return JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as SessionUser;
  } catch {
    return null;
  }
}

export async function setDemoSession(user: SessionUser): Promise<void> {
  const cookieStore = await cookies();
  const payload = Buffer.from(JSON.stringify(user)).toString("base64url");
  cookieStore.set(COOKIE_NAME, `${payload}.${sign(payload)}`, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/"
  });
}

export async function clearSession(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(COOKIE_NAME);
}

function sign(payload: string): string {
  return createHmac("sha256", sessionSecret()).update(payload).digest("base64url");
}

function verifySignature(payload: string, signature: string): boolean {
  const expected = Buffer.from(sign(payload));
  const actual = Buffer.from(signature);
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}

function sessionSecret(): string {
  return process.env.APP_SESSION_SECRET || "local-development-only-change-me";
}
