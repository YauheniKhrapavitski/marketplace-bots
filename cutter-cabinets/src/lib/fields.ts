export const CUTTER_FIELDS = [
  { key: "date", label: "Дата", kind: "date" },
  { key: "vinylstudioArticle", label: "Артикул Vinylstudio", kind: "text" },
  { key: "name", label: "Наименование", kind: "text" },
  { key: "productComment", label: "Комментарий по товарам (раскладки)", kind: "multiline" },
  { key: "shipmentNumber", label: "Номер отправления Ozon/WB", kind: "text" },
  { key: "quantity", label: "Количество", kind: "number" },
  { key: "warehouse", label: "Склад", kind: "text" },
  { key: "wildberriesArticle", label: "Артикул Wildberries", kind: "text" },
  { key: "shipmentComment", label: "Комментарий по отгрузке", kind: "multiline" },
  { key: "status", label: "Сделано/Не сделано", kind: "status" },
  { key: "complexity", label: "Коэффициент сложности", kind: "number" },
  { key: "marketplace", label: "Маркетплейс", kind: "text" },
  { key: "fulfillmentType", label: "Для расчета ФБО или ФБС", kind: "text" },
  { key: "packaging", label: "Коробки/Упаковка", kind: "text" },
  { key: "requestNumber", label: "№ Заявки", kind: "text" }
] as const;

export type CutterFieldKey = (typeof CUTTER_FIELDS)[number]["key"];

export type CutterPayload = Record<CutterFieldKey, string | number | null>;

export const CUTTER_FIELD_KEYS = CUTTER_FIELDS.map((field) => field.key);
