"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";

export function LogoutButton() {
  const router = useRouter();

  async function logout(): Promise<void> {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <button className="icon-button" type="button" aria-label="Выйти" onClick={logout}>
      <LogOut size={18} aria-hidden="true" />
    </button>
  );
}
