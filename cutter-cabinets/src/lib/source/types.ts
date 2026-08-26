import type { RawSheetRow } from "@/lib/sync/normalize";

export type SourceProvider = "google" | "microsoft";

export type SourceTab = {
  sheetName: string;
  rows: RawSheetRow[];
};

export interface SpreadsheetSourceAdapter {
  readAllowedTabs(sheetNames: string[]): Promise<SourceTab[]>;
}
