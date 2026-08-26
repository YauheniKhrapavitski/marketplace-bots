import type { SourceTab, SpreadsheetSourceAdapter } from "@/lib/source/types";

type GoogleSheetsOptions = {
  spreadsheetId: string;
  accessToken: string;
};

export class GoogleSheetsReadOnlyAdapter implements SpreadsheetSourceAdapter {
  private readonly spreadsheetId: string;
  private readonly accessToken: string;

  constructor(options: GoogleSheetsOptions) {
    this.spreadsheetId = options.spreadsheetId;
    this.accessToken = options.accessToken;
  }

  async readAllowedTabs(sheetNames: string[]): Promise<SourceTab[]> {
    return Promise.all(sheetNames.map((sheetName) => this.readTab(sheetName)));
  }

  private async readTab(sheetName: string): Promise<SourceTab> {
    const range = encodeURIComponent(`'${sheetName}'!A2:P`);
    const url = `https://sheets.googleapis.com/v4/spreadsheets/${this.spreadsheetId}/values/${range}?valueRenderOption=FORMATTED_VALUE`;
    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${this.accessToken}`
      },
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error(`Google Sheets read failed for ${sheetName}: ${response.status}`);
    }

    const payload = (await response.json()) as { values?: unknown[][] };
    const rows = (payload.values ?? []).map((values, index) => ({
      sheetName,
      rowNumber: index + 2,
      values
    }));

    return { sheetName, rows };
  }
}
