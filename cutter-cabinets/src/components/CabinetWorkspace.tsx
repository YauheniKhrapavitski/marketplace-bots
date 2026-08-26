"use client";

import { useMemo, useState } from "react";

import type { CabinetItem } from "@/lib/items";
import { CUTTER_FIELDS } from "@/lib/fields";
import { TaskTable } from "@/components/TaskTable";

type CabinetWorkspaceProps = {
  initialItems: CabinetItem[];
};

export function CabinetWorkspace({ initialItems }: CabinetWorkspaceProps) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [marketplace, setMarketplace] = useState("all");
  const [showChangedOnly, setShowChangedOnly] = useState(false);
  const [items, setItems] = useState(initialItems);

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return items.filter((item) => {
      const values = item.visible;
      const searchable = [
        values.vinylstudioArticle,
        values.wildberriesArticle,
        values.name,
        values.shipmentNumber,
        values.requestNumber
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      if (normalizedQuery && !searchable.includes(normalizedQuery)) {
        return false;
      }

      if (status !== "all" && values.status !== status) {
        return false;
      }

      if (marketplace !== "all" && values.marketplace !== marketplace) {
        return false;
      }

      if (showChangedOnly && item.changedFields.length === 0) {
        return false;
      }

      return true;
    });
  }, [items, marketplace, query, showChangedOnly, status]);

  function markDone(itemId: string): void {
    setItems((current) =>
      current.map((item) => {
        if (item.id !== itemId) {
          return item;
        }

        return {
          ...item,
          visible: { ...item.visible, status: "Сделано" },
          changedFields: Array.from(new Set([...item.changedFields, "status"]))
        };
      })
    );
  }

  function resetRow(itemId: string): void {
    setItems((current) =>
      current.map((item) =>
        item.id === itemId
          ? { ...item, visible: { ...item.sourcePayload }, changedFields: [] }
          : item
      )
    );
  }

  return (
    <>
      <section className="toolbar" aria-label="Фильтры и поиск">
        <label className="search">
          <span>Поиск</span>
          <input
            placeholder="Артикул, наименование, отправление или заявка"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <select aria-label="Статус" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="all">Все статусы</option>
          <option value="Сделано">Сделано</option>
          <option value="Не сделано">Не сделано</option>
        </select>
        <select
          aria-label="Маркетплейс"
          value={marketplace}
          onChange={(event) => setMarketplace(event.target.value)}
        >
          <option value="all">Все маркетплейсы</option>
          <option value="WB">WB</option>
          <option value="Ozon">Ozon</option>
        </select>
        <label className="toggle-filter">
          <input
            checked={showChangedOnly}
            type="checkbox"
            onChange={(event) => setShowChangedOnly(event.target.checked)}
          />
          Только измененные
        </label>
      </section>
      <TaskTable
        fields={CUTTER_FIELDS}
        items={filteredItems}
        onMarkDone={markDone}
        onResetRow={resetRow}
      />
    </>
  );
}
