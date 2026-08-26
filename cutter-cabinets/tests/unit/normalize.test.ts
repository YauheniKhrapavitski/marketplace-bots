import { describe, expect, it } from "vitest";

import { normalizeSheetRow } from "@/lib/sync/normalize";

describe("normalizeSheetRow", () => {
  it("maps columns A:O and ignores service columns after source uid", () => {
    const row = normalizeSheetRow({
      sheetName: "Китасов Саша",
      rowNumber: 7,
      values: [
        "03.08.2026",
        " VS-1 ",
        "Товар",
        "Комментарий",
        "000123",
        2,
        "Склад",
        "WB-1",
        "Отгрузка",
        "Не сделано",
        1.25,
        "WB",
        "ФБС",
        "Коробка",
        "REQ-1",
        "uuid-1",
        "служебная колонка"
      ]
    });

    expect(row.sourceUid).toBe("uuid-1");
    expect(row.sourceRowRef).toBe("Китасов Саша!7:7");
    expect(row.payload.shipmentNumber).toBe("000123");
    expect(row.payload.packaging).toBe("Коробка");
    expect(Object.keys(row.payload)).toHaveLength(15);
  });

  it("falls back to a deterministic uid when hidden uid is absent", () => {
    const row = normalizeSheetRow({
      sheetName: "Жулега Паша",
      rowNumber: 3,
      values: ["03.08.2026", "VS-2", "Товар", "", "", 1, "", "", "", "", "", "", "", "", "REQ-2"]
    });

    expect(row.sourceUid).toBe("Жулега Паша:REQ-2");
  });
});
