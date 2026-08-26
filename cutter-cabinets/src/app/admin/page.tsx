import { redirect } from "next/navigation";

import { Header } from "@/components/Header";
import { AdminSyncButton } from "@/components/AdminSyncButton";
import { readSessionUser } from "@/lib/auth/session";

const cutters = [
  ["Китасов Саша", "kitasov", "Китасов Саша", "Активен"],
  ["Лазаревич Андрей", "lazarevich", "Лазаревич Андрей", "Активен"],
  ["Жулега Паша", "zhulega", "Жулега Паша", "Активен"],
  ["Шараев Андрей", "sharaev", "Шараев Андрей", "Активен"],
  ["Окуневец Никита", "okunevets", "Окуневец Никита", "Активен"],
  ["Титоров Максим", "titorov", "Титоров Максим", "Активен"]
];

export const dynamic = "force-dynamic";

export default async function AdminPage() {
  const session = await readSessionUser();
  if (!session) {
    redirect("/login");
  }

  if (session.role !== "ADMIN") {
    redirect("/");
  }

  return (
    <main className="app-shell">
      <Header active="admin" userName={session.displayName} />
      <section className="admin-grid">
        <div className="panel">
          <h2>Пользователи и вкладки</h2>
          <table className="admin-table">
            <thead>
              <tr>
                <th>ФИО</th>
                <th>Логин</th>
                <th>Вкладка</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {cutters.map(([name, login, sheet, status]) => (
                <tr key={login}>
                  <td>{name}</td>
                  <td>{login}</td>
                  <td>{sheet}</td>
                  <td>{status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="panel">
          <h2>Синхронизация</h2>
          <dl className="facts">
            <dt>Провайдер</dt>
            <dd>Google Sheets</dd>
            <dt>Режим</dt>
            <dd>Только чтение</dd>
            <dt>Интервал</dt>
            <dd>1-5 минут</dd>
          </dl>
          <AdminSyncButton />
        </div>
      </section>
    </main>
  );
}
