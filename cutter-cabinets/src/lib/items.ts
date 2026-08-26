import type { CutterPayload } from "@/lib/fields";
import { getMergedDemoItems } from "@/lib/demo-data";
import { prisma } from "@/lib/db/client";
import { mergeSourceWithOverrides, type FieldOverride } from "@/lib/sync/merge";
import type { SessionUser } from "@/lib/auth/session";

export type CabinetItem = {
  id: string;
  sourceUid: string;
  sourceSheet: string;
  sourceRowRef: string;
  sourcePayload: CutterPayload;
  visible: CutterPayload;
  changedFields: Array<keyof CutterPayload>;
  isArchived: boolean;
  syncedAt: string;
};

export type CabinetDataset = {
  items: CabinetItem[];
  source: "database" | "demo";
  lastSuccessfulSyncAt: string | null;
};

export async function getCabinetDataset(session: SessionUser | null): Promise<CabinetDataset> {
  try {
    if (!session?.cutterId && session?.role !== "ADMIN") {
      return demoDataset();
    }

    const items = await prisma.sourceItem.findMany({
      where:
        session.role === "ADMIN"
          ? { isArchived: false }
          : { cutterId: session.cutterId, isArchived: false },
      include: { overrides: true },
      orderBy: [{ syncedAt: "desc" }],
      take: 50
    });

    const connection = await prisma.sourceConnection.findFirst({
      orderBy: { updatedAt: "desc" }
    });

    return {
      items: items.map((item) => {
        const sourcePayload = item.sourcePayload as CutterPayload;
        const merged = mergeSourceWithOverrides(
          sourcePayload,
          item.overrides.map((override) => ({
            fieldName: override.fieldName as FieldOverride["fieldName"],
            value: override.value as FieldOverride["value"]
          }))
        );

        return {
          id: item.id,
          sourceUid: item.sourceUid,
          sourceSheet: item.sourceSheet,
          sourceRowRef: item.sourceRowRef,
          sourcePayload,
          visible: merged.visible,
          changedFields: merged.changedFields,
          isArchived: item.isArchived,
          syncedAt: item.syncedAt.toISOString()
        };
      }),
      source: "database",
      lastSuccessfulSyncAt: connection?.lastSuccessfulSyncAt?.toISOString() ?? null
    };
  } catch {
    return demoDataset();
  }
}

function demoDataset(): CabinetDataset {
  return {
    items: getMergedDemoItems().map((item) => ({
      ...item,
      sourcePayload: item.sourcePayload,
      syncedAt: item.syncedAt
    })),
    source: "demo",
    lastSuccessfulSyncAt: new Date("2026-08-03T09:03:00.000Z").toISOString()
  };
}
