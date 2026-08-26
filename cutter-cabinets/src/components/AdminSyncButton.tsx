"use client";

import { useState } from "react";
import { Play } from "lucide-react";

export function AdminSyncButton() {
  const [message, setMessage] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  async function runSync(): Promise<void> {
    setIsRunning(true);
    setMessage(null);

    const response = await fetch("/api/admin/sync", { method: "POST" });
    const payload = (await response.json()) as { message?: string; error?: string; correlationId?: string };

    setIsRunning(false);
    if (!response.ok) {
      setMessage(payload.error ?? "Не удалось запустить синхронизацию");
      return;
    }

    setMessage(`${payload.message} ID: ${payload.correlationId}`);
  }

  return (
    <div className="sync-action">
      <button className="primary-button" type="button" onClick={runSync} disabled={isRunning}>
        <Play size={17} aria-hidden="true" />
        {isRunning ? "Запускаем..." : "Запустить sync"}
      </button>
      {message ? <p className="sync-message">{message}</p> : null}
    </div>
  );
}
