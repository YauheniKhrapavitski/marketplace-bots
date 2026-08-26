import type { CUTTER_FIELDS, CutterPayload } from "@/lib/fields";

type Field = (typeof CUTTER_FIELDS)[number];

type TaskTableProps = {
  fields: readonly Field[];
  items: Array<{
    id: string;
    sourceUid: string;
    visible: CutterPayload;
    changedFields: Array<keyof CutterPayload>;
    isArchived: boolean;
  }>;
  onMarkDone?: (itemId: string) => void;
  onResetRow?: (itemId: string) => void;
};

export function TaskTable({ fields, items, onMarkDone, onResetRow }: TaskTableProps) {
  return (
    <section className="table-wrap" aria-label="Задания резчика">
      <table className="task-table">
        <thead>
          <tr>
            {fields.map((field) => (
              <th key={field.key}>{field.label}</th>
            ))}
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className={item.isArchived ? "archived-row" : undefined}>
              {fields.map((field) => {
                const changed = item.changedFields.includes(field.key);
                return (
                  <td key={field.key} className={changed ? "changed-cell" : undefined}>
                    <span title={changed ? "Изменено в личном кабинете" : undefined}>
                      {formatValue(item.visible[field.key])}
                    </span>
                  </td>
                );
              })}
              <td>
                <div className="row-actions">
                  <button className="small-button" type="button" onClick={() => onMarkDone?.(item.id)}>
                    Сделано
                  </button>
                  <button className="small-button" type="button" onClick={() => onResetRow?.(item.id)}>
                    Сброс
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function formatValue(value: string | number | null): string {
  if (value === null || value === "") {
    return "";
  }

  return String(value);
}
