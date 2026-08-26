import { Prisma } from "@prisma/client";
import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";

import { CUTTER_FIELD_KEYS } from "@/lib/fields";
import { readSessionUser } from "@/lib/auth/session";
import { prisma } from "@/lib/db/client";

const overrideSchema = z.object({
  fieldName: z.enum(CUTTER_FIELD_KEYS as [string, ...string[]]),
  value: z.union([z.string(), z.number(), z.null()])
});

type RouteContext = {
  params: Promise<{ id: string }>;
};

export async function PATCH(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const session = await readSessionUser();
  if (!session) {
    return NextResponse.json({ error: "Требуется вход" }, { status: 401 });
  }

  const parsed = overrideSchema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Некорректное поле изменения" }, { status: 400 });
  }

  const { id } = await context.params;
  const overrideValue = parsed.data.value === null ? Prisma.JsonNull : parsed.data.value;

  try {
    const item = await prisma.sourceItem.findUnique({ where: { id } });
    if (!item || (session.role !== "ADMIN" && item.cutterId !== session.cutterId)) {
      return NextResponse.json({ error: "Задание не найдено" }, { status: 404 });
    }

    const override = await prisma.itemOverride.upsert({
      where: { itemId_fieldName: { itemId: id, fieldName: parsed.data.fieldName } },
      update: { value: overrideValue, updatedBy: session.id, cutterId: item.cutterId },
      create: {
        itemId: id,
        cutterId: item.cutterId,
        fieldName: parsed.data.fieldName,
        value: overrideValue,
        updatedBy: session.id
      }
    });

    return NextResponse.json({ override });
  } catch {
    return NextResponse.json(
      { error: "БД недоступна. В демо-режиме изменения применяются только на экране." },
      { status: 503 }
    );
  }
}

export async function DELETE(_request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const session = await readSessionUser();
  if (!session) {
    return NextResponse.json({ error: "Требуется вход" }, { status: 401 });
  }

  const { id } = await context.params;

  try {
    const item = await prisma.sourceItem.findUnique({ where: { id } });
    if (!item || (session.role !== "ADMIN" && item.cutterId !== session.cutterId)) {
      return NextResponse.json({ error: "Задание не найдено" }, { status: 404 });
    }

    await prisma.itemOverride.deleteMany({ where: { itemId: id } });
    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json(
      { error: "БД недоступна. В демо-режиме сброс применяется только на экране." },
      { status: 503 }
    );
  }
}
