"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Alert } from "@/components/Alert";
import { api, ApiError } from "@/lib/api";
import { formatDate, statusClass, statusLabel } from "@/lib/format";
import type { LeaderboardResponse } from "@/lib/types";

function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Неизвестная ошибка";
}

export default function LeaderboardPage() {
  const params = useParams<{ gameId: string }>();
  const gameId = decodeURIComponent(params.gameId);
  const [data, setData] = useState<LeaderboardResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [exchange, setExchange] = useState<number | "all">("all");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await api.leaderboard(gameId));
      setMessage(null);
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => {
      void load();
    }, 10000);
    return () => window.clearInterval(id);
  }, [load]);

  const exchanges = useMemo(() => {
    if (!data) return [];
    return Array.from(new Set(data.tasks.map((task) => task.exchange))).sort((a, b) => a - b);
  }, [data]);

  const tasks = useMemo(() => {
    if (!data) return [];
    if (exchange === "all") return data.tasks;
    return data.tasks.filter((task) => task.exchange === exchange);
  }, [data, exchange]);

  return (
    <div className="vstack gap-4">
      <div className="panel p-4">
        <div className="d-flex flex-wrap justify-content-between align-items-start gap-3">
          <div>
            <div className="d-flex align-items-center gap-2 mb-2">
              <h1 className="h3 mb-0">Рейтинг {gameId}</h1>
              {data ? <span className={`badge ${statusClass(data.status)}`}>{statusLabel(data.status)}</span> : null}
            </div>
            <p className="muted mb-0">Обновляется автоматически каждые 10 секунд.</p>
          </div>
          <button className="btn btn-outline-primary" onClick={() => void load()} disabled={loading} type="button">
            {loading ? "Обновление..." : "Обновить"}
          </button>
        </div>
      </div>

      <Alert message={message} />

      {data ? (
        <>
          <div className="panel p-0 overflow-hidden">
            <div className="p-3 border-bottom d-flex justify-content-between align-items-center">
              <h2 className="h5 mb-0">Команды</h2>
              <span className="muted small">{data.players.length} участников</span>
            </div>
            <div className="table-responsive">
              <table className="table table-hover align-middle mb-0">
                <thead className="table-light">
                  <tr>
                    <th>Место</th>
                    <th>Команда</th>
                    <th className="text-end">Очки</th>
                    <th className="text-end">Решения</th>
                    <th className="text-end">Попытки</th>
                    <th>Последнее решение</th>
                  </tr>
                </thead>
                <tbody>
                  {data.players.map((player) => (
                    <tr key={player.player_id}>
                      <td className="fw-semibold">{player.rank}</td>
                      <td>
                        <div className="fw-semibold">{player.team_name}</div>
                        <div className="muted small">{player.members.join(", ") || "без состава"}</div>
                      </td>
                      <td className="text-end fw-semibold">{player.score}</td>
                      <td className="text-end">{player.solves}</td>
                      <td className="text-end">
                        {player.attempts}
                        <span className="muted"> / {player.wrong_attempts} неверных</span>
                      </td>
                      <td>{formatDate(player.last_solve_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="d-flex flex-wrap align-items-center justify-content-between gap-3">
            <h2 className="h4 mb-0">Рынок задач</h2>
            <ul className="nav nav-pills gap-2">
              <li className="nav-item">
                <button className={`nav-link ${exchange === "all" ? "active" : ""}`} type="button" onClick={() => setExchange("all")}>
                  Все
                </button>
              </li>
              {exchanges.map((item) => (
                <li className="nav-item" key={item}>
                  <button className={`nav-link ${exchange === item ? "active" : ""}`} type="button" onClick={() => setExchange(item)}>
                    Биржа {item}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="row g-3">
            {tasks.map((task) => (
              <div className="col-md-6 col-xl-4" key={`${task.task_id}-${task.exchange}`}>
                <div className="panel p-3 h-100">
                  <div className="d-flex justify-content-between gap-3 mb-2">
                    <div>
                      <div className="fw-semibold">
                        {task.name} · биржа {task.exchange}
                      </div>
                      <div className="muted small">ID {task.task_id}</div>
                    </div>
                    <span className="price-pill">{task.current_cost}</span>
                  </div>
                  <div className="task-statement muted mb-3">{task.statement || "Условие пустое"}</div>
                  <div className="d-flex flex-wrap gap-2 mb-3">
                    <span className="badge text-bg-light">решений: {task.solves}</span>
                    <span className="badge text-bg-light">попыток: {task.attempts}</span>
                    <span className="badge text-bg-light">ошибок: {task.wrong_attempts}</span>
                  </div>
                  <div className="small">
                    {task.solved_by.length ? (
                      task.solved_by.map((solve) => (
                        <div className="d-flex justify-content-between gap-2" key={`${solve.player_id}-${solve.solved_at}`}>
                          <span>{solve.team_name}</span>
                          <span className="muted">+{solve.cost}</span>
                        </div>
                      ))
                    ) : (
                      <span className="muted">Пока без решений</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
