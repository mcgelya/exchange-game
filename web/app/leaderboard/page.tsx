"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function LeaderboardEntryPage() {
  const [gameId, setGameId] = useState("");
  const router = useRouter();

  function openLeaderboard(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (gameId.trim()) {
      router.push(`/leaderboard/${encodeURIComponent(gameId.trim())}`);
    }
  }

  return (
    <div className="row justify-content-center">
      <div className="col-md-7 col-lg-5">
        <div className="panel p-4">
          <h1 className="h3 mb-2">Публичный рейтинг</h1>
          <p className="muted mb-4">Введи ID игры, чтобы открыть таблицу команд и рынок задач.</p>
          <form onSubmit={openLeaderboard} className="d-flex gap-2">
            <input className="form-control" value={gameId} onChange={(event) => setGameId(event.target.value)} placeholder="G-ABCDEF12" required />
            <button className="btn btn-primary" type="submit">
              Открыть
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
