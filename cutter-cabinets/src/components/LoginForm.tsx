"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function LoginForm() {
  const router = useRouter();
  const [login, setLogin] = useState("cutter");
  const [password, setPassword] = useState("cutter");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login, password })
    });
    const payload = (await response.json()) as { error?: string; redirectTo?: string };

    setIsSubmitting(false);
    if (!response.ok) {
      setError(payload.error ?? "Не удалось войти");
      return;
    }

    router.push(payload.redirectTo ?? "/");
    router.refresh();
  }

  return (
    <form className="login-form" onSubmit={submit}>
      <h1>Вход в кабинет</h1>
      <p className="form-note">Демо-доступ: `cutter/cutter` или `admin/admin`.</p>
      <label>
        Логин
        <input
          name="login"
          autoComplete="username"
          value={login}
          onChange={(event) => setLogin(event.target.value)}
        />
      </label>
      <label>
        Пароль
        <input
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </label>
      {error ? <p className="form-error">{error}</p> : null}
      <button className="primary-button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Входим..." : "Войти"}
      </button>
    </form>
  );
}
