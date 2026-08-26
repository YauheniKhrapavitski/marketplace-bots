import { NextResponse } from "next/server";

import { readSessionUser } from "@/lib/auth/session";
import { stableChecksum } from "@/lib/sync/checksum";

export async function POST(): Promise<NextResponse> {
  const session = await readSessionUser();
  if (!session) {
    return NextResponse.json({ error: "Требуется вход" }, { status: 401 });
  }

  if (session.role !== "ADMIN") {
    return NextResponse.json({ error: "Требуется роль администратора" }, { status: 403 });
  }

  return NextResponse.json({
    status: "accepted",
    provider: process.env.SOURCE_PROVIDER ?? "google",
    mode: "read-only",
    correlationId: stableChecksum(`${Date.now()}:${Math.random()}`).slice(0, 16),
    message: "Синхронизация поставлена в очередь. В этом срезе подключен безопасный read-only каркас."
  });
}
