import { redirect } from "next/navigation";

import { Header } from "@/components/Header";
import { StatusBar } from "@/components/StatusBar";
import { CabinetWorkspace } from "@/components/CabinetWorkspace";
import { readSessionUser } from "@/lib/auth/session";
import { getCabinetDataset } from "@/lib/items";

export const dynamic = "force-dynamic";

export default async function CutterCabinetPage() {
  const session = await readSessionUser();
  if (!session) {
    redirect("/login");
  }

  const dataset = await getCabinetDataset(session);
  const syncedAt = dataset.lastSuccessfulSyncAt
    ? new Intl.DateTimeFormat("ru-RU", {
        dateStyle: "short",
        timeStyle: "short",
        timeZone: "Europe/Moscow"
      }).format(new Date(dataset.lastSuccessfulSyncAt))
    : "нет успешных запусков";

  return (
    <main className="app-shell">
      <Header active="cabinet" userName={session.displayName} />
      <StatusBar
        syncedAt={syncedAt}
        sourceStatus={
          dataset.source === "database"
            ? "PostgreSQL: реальные данные"
            : "Демо-режим: БД не подключена"
        }
      />
      <CabinetWorkspace initialItems={dataset.items} />
    </main>
  );
}
