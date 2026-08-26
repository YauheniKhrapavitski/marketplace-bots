type StatusBarProps = {
  syncedAt: string;
  sourceStatus: string;
};

export function StatusBar({ syncedAt, sourceStatus }: StatusBarProps) {
  return (
    <section className="status-bar" aria-label="Статус источника">
      <span>Последняя успешная синхронизация: {syncedAt}</span>
      <span>{sourceStatus}</span>
      <span>Изменения резчика хранятся только в веб-копии</span>
    </section>
  );
}
