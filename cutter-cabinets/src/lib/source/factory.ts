import { GoogleSheetsReadOnlyAdapter } from "@/lib/source/googleSheets";
import type { SourceProvider, SpreadsheetSourceAdapter } from "@/lib/source/types";

export function createSourceAdapter(provider: SourceProvider): SpreadsheetSourceAdapter {
  if (provider === "google") {
    const spreadsheetId = process.env.SOURCE_SPREADSHEET_ID;
    const accessToken = process.env.GOOGLE_ACCESS_TOKEN;

    if (!spreadsheetId || !accessToken) {
      throw new Error("Google Sheets source requires SOURCE_SPREADSHEET_ID and GOOGLE_ACCESS_TOKEN");
    }

    return new GoogleSheetsReadOnlyAdapter({ spreadsheetId, accessToken });
  }

  throw new Error("Microsoft source adapter is planned but not implemented in this slice");
}
