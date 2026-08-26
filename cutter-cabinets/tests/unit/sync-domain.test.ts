import { describe, expect, it } from "vitest";

import type { CutterPayload } from "@/lib/fields";
import { findItemsToArchive } from "@/lib/sync/archive";
import { stableChecksum } from "@/lib/sync/checksum";
import { mergeSourceWithOverrides } from "@/lib/sync/merge";

const source: CutterPayload = {
  date: "03.08.2026",
  vinylstudioArticle: "VS-1",
  name: "Товар",
  productComment: "Исходный комментарий",
  shipmentNumber: "000123",
  quantity: 1,
  warehouse: "Склад",
  wildberriesArticle: "WB-1",
  shipmentComment: "Исходная отгрузка",
  status: "Не сделано",
  complexity: 1.5,
  marketplace: "WB",
  fulfillmentType: "ФБС",
  packaging: "Коробка",
  requestNumber: "REQ-1"
};

describe("sync domain", () => {
  it("keeps cutter overrides above source snapshot", () => {
    const merged = mergeSourceWithOverrides(source, [
      { fieldName: "status", value: "Сделано" },
      { fieldName: "productComment", value: "Личный комментарий" }
    ]);

    expect(merged.visible.status).toBe("Сделано");
    expect(merged.visible.productComment).toBe("Личный комментарий");
    expect(merged.visible.name).toBe("Товар");
    expect(merged.changedFields).toEqual(["status", "productComment"]);
  });

  it("produces stable checksums regardless of object key order", () => {
    expect(stableChecksum({ b: 2, a: 1 })).toBe(stableChecksum({ a: 1, b: 2 }));
  });

  it("archives only active items missing from incoming source", () => {
    const archived = findItemsToArchive(
      [
        { sourceUid: "one", isArchived: false },
        { sourceUid: "two", isArchived: false },
        { sourceUid: "old", isArchived: true }
      ],
      ["two"]
    );

    expect(archived).toEqual(["one"]);
  });
});
