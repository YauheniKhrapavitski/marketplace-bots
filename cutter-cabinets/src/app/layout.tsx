import type { Metadata } from "next";

import "./styles.css";

export const metadata: Metadata = {
  title: "Кабинеты резчиков",
  description: "Личные рабочие копии заданий резчиков из Google Sheets"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
