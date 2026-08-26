import type { CutterPayload } from "@/lib/fields";
import { mergeSourceWithOverrides } from "@/lib/sync/merge";

export type DemoItem = {
  id: string;
  sourceUid: string;
  sourceSheet: string;
  sourceRowRef: string;
  sourcePayload: CutterPayload;
  overrides: Array<{ fieldName: keyof CutterPayload; value: string | number | null }>;
  isArchived: boolean;
  syncedAt: string;
};

const demoSourcePayload: CutterPayload = {
  date: "03.08.2026",
  vinylstudioArticle: "VS-1042",
  name: "Наклейка декоративная, тестовый набор",
  productComment: "Проверить раскладку перед резкой",
  shipmentNumber: "000734512",
  quantity: 2,
  warehouse: "Коледино",
  wildberriesArticle: "WB-990012",
  shipmentComment: "Отгрузить отдельной коробкой",
  status: "Не сделано",
  complexity: 1.25,
  marketplace: "WB",
  fulfillmentType: "ФБС",
  packaging: "Коробка S",
  requestNumber: "REQ-2026-0001"
};

export const demoItems: DemoItem[] = [
  {
    id: "demo-1",
    sourceUid: "demo-source-1",
    sourceSheet: "Китасов Саша",
    sourceRowRef: "Китасов Саша!2:2",
    sourcePayload: demoSourcePayload,
    overrides: [{ fieldName: "status", value: "Сделано" }],
    isArchived: false,
    syncedAt: new Date("2026-08-03T09:00:00.000Z").toISOString()
  },
  {
    id: "demo-2",
    sourceUid: "demo-source-2",
    sourceSheet: "Китасов Саша",
    sourceRowRef: "Китасов Саша!3:3",
    sourcePayload: {
      ...demoSourcePayload,
      vinylstudioArticle: "VS-2048",
      name: "Комплект этикеток для тестовой витрины",
      status: "Не сделано",
      requestNumber: "REQ-2026-0002"
    },
    overrides: [],
    isArchived: false,
    syncedAt: new Date("2026-08-03T09:03:00.000Z").toISOString()
  }
];

export function getMergedDemoItems(): Array<DemoItem & ReturnType<typeof mergeSourceWithOverrides>> {
  return demoItems.map((item) => ({
    ...item,
    ...mergeSourceWithOverrides(item.sourcePayload, item.overrides)
  }));
}
