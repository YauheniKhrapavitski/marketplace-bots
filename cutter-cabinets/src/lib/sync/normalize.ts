import { CUTTER_FIELD_KEYS, type CutterPayload } from "@/lib/fields";

export type RawSheetRow = {
  sheetName: string;
  rowNumber: number;
  values: unknown[];
};

export type NormalizedSourceRow = {
  sourceUid: string;
  sourceSheet: string;
  sourceRowRef: string;
  payload: CutterPayload;
};

const SOURCE_UID_COLUMN_INDEX = 15;

export function normalizeSheetRow(row: RawSheetRow): NormalizedSourceRow {
  const values = row.values.slice(0, CUTTER_FIELD_KEYS.length);
  const payload = CUTTER_FIELD_KEYS.reduce<CutterPayload>((acc, key, index) => {
    acc[key] = normalizeCell(values[index]);
    return acc;
  }, {} as CutterPayload);

  const explicitSourceUid = normalizeCell(row.values[SOURCE_UID_COLUMN_INDEX]);
  const fallbackUid = `${row.sheetName}:${payload.requestNumber || payload.shipmentNumber || row.rowNumber}`;

  return {
    sourceUid: String(explicitSourceUid || fallbackUid),
    sourceSheet: row.sheetName,
    sourceRowRef: `${row.sheetName}!${row.rowNumber}:${row.rowNumber}`,
    payload
  };
}

function normalizeCell(value: unknown): string | number | null {
  if (value === undefined || value === null) {
    return null;
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  if (typeof value === "boolean") {
    return value ? "Да" : "Нет";
  }

  const text = String(value).trim();
  return text.length > 0 ? text : null;
}
