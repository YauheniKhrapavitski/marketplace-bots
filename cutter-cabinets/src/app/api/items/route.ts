import { NextResponse } from "next/server";

import { readSessionUser } from "@/lib/auth/session";
import { getCabinetDataset } from "@/lib/items";

export async function GET(): Promise<NextResponse> {
  const session = await readSessionUser();
  if (!session) {
    return NextResponse.json({ error: "Требуется вход" }, { status: 401 });
  }

  const dataset = await getCabinetDataset(session);
  return NextResponse.json({
    items: dataset.items,
    page: 1,
    pageSize: 50,
    total: dataset.items.length,
    source: dataset.source
  });
}
