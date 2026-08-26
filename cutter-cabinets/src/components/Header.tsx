import Link from "next/link";
import { RefreshCw, Settings, Table2 } from "lucide-react";
import { LogoutButton } from "@/components/LogoutButton";

type HeaderProps = {
  active: "cabinet" | "admin";
  userName?: string;
};

export function Header({ active, userName }: HeaderProps) {
  return (
    <header className="header">
      <div>
        <p className="eyebrow">Веб-копия заданий</p>
        <h1>Кабинеты резчиков</h1>
      </div>
      <nav aria-label="Основная навигация">
        {userName ? <span className="user-chip">{userName}</span> : null}
        <Link className={active === "cabinet" ? "nav-link active" : "nav-link"} href="/">
          <Table2 size={18} aria-hidden="true" />
          Кабинет
        </Link>
        <Link className={active === "admin" ? "nav-link active" : "nav-link"} href="/admin">
          <Settings size={18} aria-hidden="true" />
          Админ
        </Link>
        <button className="icon-button" type="button" aria-label="Обновить синхронизацию">
          <RefreshCw size={18} aria-hidden="true" />
        </button>
        {userName ? <LogoutButton /> : null}
      </nav>
    </header>
  );
}
