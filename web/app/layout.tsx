import "bootstrap/dist/css/bootstrap.min.css";
import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Exchange Game",
  description: "Team math exchange game frontend"
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ru">
      <body>
        <div className="app-shell">
          <nav className="topbar sticky-top">
            <div className="container py-3 d-flex align-items-center justify-content-between gap-3">
              <Link className="navbar-brand d-flex align-items-center gap-2 m-0" href="/">
                <span className="brand-mark">E</span>
                <span className="fw-semibold">Exchange Game</span>
              </Link>
              <div className="d-flex align-items-center gap-2">
                <Link className="btn btn-sm btn-outline-primary" href="/">
                  Игрок
                </Link>
                <Link className="btn btn-sm btn-outline-secondary" href="/leaderboard">
                  Рейтинг
                </Link>
                <Link className="btn btn-sm btn-dark" href="/admin">
                  Админка
                </Link>
              </div>
            </div>
          </nav>
          <main className="container py-4 py-lg-5">{children}</main>
        </div>
      </body>
    </html>
  );
}
