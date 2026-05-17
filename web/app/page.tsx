"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Alert } from "@/components/Alert";
import { LoadingButton } from "@/components/LoadingButton";
import { api, ApiError } from "@/lib/api";
import { formatDate, statusClass, statusLabel } from "@/lib/format";
import type { StatusResponse, SubmitResponse, TaskStatus } from "@/lib/types";

const TOKEN_KEY = "exchange-game-player-token";

function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Неизвестная ошибка";
}

function splitMembers(value: string) {
  return value
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function PlayerPage() {
  const [token, setToken] = useState("");
  const [savedToken, setSavedToken] = useState("");
  const [gameId, setGameId] = useState("");
  const [teamName, setTeamName] = useState("");
  const [members, setMembers] = useState("");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [activeExchange, setActiveExchange] = useState<number | "all">("all");
  const [message, setMessage] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [registering, setRegistering] = useState(false);

  const loadStatus = useCallback(
    async (playerToken = savedToken) => {
      if (!playerToken) return;
      setLoadingStatus(true);
      try {
        const nextStatus = await api.status(playerToken);
        setStatus(nextStatus);
        setMessage(null);
      } catch (error) {
        setMessage(errorMessage(error));
      } finally {
        setLoadingStatus(false);
      }
    },
    [savedToken]
  );

  useEffect(() => {
    const stored = window.localStorage.getItem(TOKEN_KEY) || "";
    if (stored) {
      setSavedToken(stored);
      setToken(stored);
      void loadStatus(stored);
    }
  }, [loadStatus]);

  useEffect(() => {
    if (!savedToken) return;
    const id = window.setInterval(() => {
      void loadStatus(savedToken);
    }, 10000);
    return () => window.clearInterval(id);
  }, [loadStatus, savedToken]);

  const exchanges = useMemo(() => {
    if (!status) return [];
    return Array.from({ length: status.game.exchanges }, (_, index) => index + 1);
  }, [status]);

  const visibleTasks = useMemo(() => {
    if (!status) return [];
    if (activeExchange === "all") return status.tasks;
    return status.tasks.filter((task) => task.exchange === activeExchange);
  }, [activeExchange, status]);

  async function register(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setRegistering(true);
    setMessage(null);
    setSuccess(null);

    try {
      const response = await api.register({
        game_id: gameId.trim(),
        team_name: teamName.trim(),
        members: splitMembers(members)
      });
      window.localStorage.setItem(TOKEN_KEY, response.token);
      setSavedToken(response.token);
      setToken(response.token);
      setSuccess(`Команда ${response.team_name} зарегистрирована`);
      await loadStatus(response.token);
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setRegistering(false);
    }
  }

  async function saveToken(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextToken = token.trim();
    window.localStorage.setItem(TOKEN_KEY, nextToken);
    setSavedToken(nextToken);
    setSuccess("Токен сохранен");
    await loadStatus(nextToken);
  }

  function logout() {
    window.localStorage.removeItem(TOKEN_KEY);
    setSavedToken("");
    setToken("");
    setStatus(null);
    setSuccess(null);
    setMessage(null);
  }

  return (
    <div className="row g-4">
      <div className="col-lg-4">
        <div className="panel p-4 mb-4">
          <h1 className="h3 mb-2">Кабинет команды</h1>
          <p className="muted mb-4">Регистрация, задачи по биржам и сдача ответов.</p>

          <Alert message={message} />
          <Alert message={success} tone="success" />

          <form onSubmit={register} className="vstack gap-3">
            <div>
              <label className="form-label">ID игры</label>
              <input className="form-control" value={gameId} onChange={(event) => setGameId(event.target.value)} placeholder="G-ABCDEF12" required />
            </div>
            <div>
              <label className="form-label">Название команды</label>
              <input className="form-control" value={teamName} onChange={(event) => setTeamName(event.target.value)} placeholder="Euler" required />
            </div>
            <div>
              <label className="form-label">Участники</label>
              <textarea className="form-control" value={members} onChange={(event) => setMembers(event.target.value)} rows={3} placeholder="Алиса, Боб" />
            </div>
            <LoadingButton loading={registering} className="btn btn-primary" type="submit">
              Зарегистрироваться
            </LoadingButton>
          </form>
        </div>

        <div className="panel p-4">
          <h2 className="h5 mb-3">Войти по токену</h2>
          <form onSubmit={saveToken} className="vstack gap-3">
            <input className="form-control" value={token} onChange={(event) => setToken(event.target.value)} placeholder="player-token" />
            <div className="d-flex gap-2">
              <LoadingButton loading={loadingStatus} className="btn btn-outline-primary flex-grow-1" type="submit">
                Открыть игру
              </LoadingButton>
              {savedToken ? (
                <button className="btn btn-outline-secondary" type="button" onClick={logout}>
                  Выйти
                </button>
              ) : null}
            </div>
          </form>
        </div>
      </div>

      <div className="col-lg-8">
        {status ? (
          <GameWorkspace
            status={status}
            activeExchange={activeExchange}
            exchanges={exchanges}
            visibleTasks={visibleTasks}
            token={savedToken}
            onExchange={setActiveExchange}
            onRefresh={() => loadStatus(savedToken)}
          />
        ) : (
          <div className="panel p-5 text-center">
            <h2 className="h4">Нет активной сессии</h2>
            <p className="muted mb-0">Зарегистрируй команду или вставь уже выданный токен.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function GameWorkspace({
  status,
  exchanges,
  visibleTasks,
  activeExchange,
  token,
  onExchange,
  onRefresh
}: {
  status: StatusResponse;
  exchanges: number[];
  visibleTasks: TaskStatus[];
  activeExchange: number | "all";
  token: string;
  onExchange: (exchange: number | "all") => void;
  onRefresh: () => Promise<void>;
}) {
  const solvedTasks = new Set(status.tasks.filter((task) => task.solved_by_me).map((task) => task.task_id));
  const totalTasks = new Set(status.tasks.map((task) => task.task_id)).size;
  const scoreByTask = new Map<number, number>();
  status.tasks.forEach((task) => {
    if (task.solved_by_me && task.my_solved_cost !== null && !scoreByTask.has(task.task_id)) {
      scoreByTask.set(task.task_id, task.my_solved_cost);
    }
  });
  const totalScore = Array.from(scoreByTask.values()).reduce((sum, cost) => sum + cost, 0);

  return (
    <div className="vstack gap-4">
      <div className="panel p-4">
        <div className="d-flex flex-wrap justify-content-between align-items-start gap-3 mb-4">
          <div>
            <div className="d-flex align-items-center gap-2 mb-2">
              <h2 className="h4 m-0">{status.player.team_name}</h2>
              <span className={`badge ${statusClass(status.game.status)}`}>{statusLabel(status.game.status)}</span>
            </div>
            <div className="muted">
              Игра {status.game_id} · пул {status.game.pool} · сервер {formatDate(status.game.server_time)}
            </div>
          </div>
          <div className="d-flex gap-2">
            <Link className="btn btn-outline-primary" href={`/leaderboard/${status.game_id}`}>
              Рейтинг
            </Link>
            <button className="btn btn-outline-secondary" type="button" onClick={() => void onRefresh()}>
              Обновить
            </button>
          </div>
        </div>

        <div className="row g-3">
          <div className="col-6 col-md-3">
            <div className="metric">
              <div className="muted small">Очки</div>
              <div className="h4 mb-0">{totalScore}</div>
            </div>
          </div>
          <div className="col-6 col-md-3">
            <div className="metric">
              <div className="muted small">Решено</div>
              <div className="h4 mb-0">
                {solvedTasks.size}/{totalTasks}
              </div>
            </div>
          </div>
          <div className="col-6 col-md-3">
            <div className="metric">
              <div className="muted small">Команды</div>
              <div className="h4 mb-0">
                {status.game.registered_players}/{status.game.players}
              </div>
            </div>
          </div>
          <div className="col-6 col-md-3">
            <div className="metric">
              <div className="muted small">Биржи</div>
              <div className="h4 mb-0">{status.game.exchanges}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="d-flex flex-wrap align-items-center justify-content-between gap-3">
        <ul className="nav nav-pills gap-2">
          <li className="nav-item">
            <button className={`nav-link ${activeExchange === "all" ? "active" : ""}`} onClick={() => onExchange("all")} type="button">
              Все
            </button>
          </li>
          {exchanges.map((exchange) => (
            <li className="nav-item" key={exchange}>
              <button className={`nav-link ${activeExchange === exchange ? "active" : ""}`} onClick={() => onExchange(exchange)} type="button">
                Биржа {exchange}
              </button>
            </li>
          ))}
        </ul>
        <span className="muted small">Цена пересчитывается на сервере</span>
      </div>

      <div className="row g-3">
        {visibleTasks.map((task) => (
          <div className="col-md-6" key={`${task.task_id}-${task.exchange}`}>
            <TaskCard task={task} token={token} onRefresh={onRefresh} />
          </div>
        ))}
      </div>
    </div>
  );
}

function TaskCard({ task, token, onRefresh }: { task: TaskStatus; token: string; onRefresh: () => Promise<void> }) {
  const [solution, setSolution] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [tone, setTone] = useState<"success" | "warning" | "danger" | "info">("info");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setResult(null);

    try {
      const response: SubmitResponse = await api.submit(token, {
        task: task.task_id,
        exchange: task.exchange,
        solution
      });
      if (response.accepted) {
        setTone("success");
        setResult(`Принято: +${response.cost}`);
        setSolution("");
      } else if (response.solved_by_me) {
        setTone("info");
        setResult(
          response.solved_exchange
            ? `Эта задача уже решена на бирже ${response.solved_exchange}`
            : "Эта задача уже решена"
        );
      } else {
        setTone("warning");
        setResult(`Неверно. Новая цена: ${response.cost}`);
      }
      await onRefresh();
    } catch (error) {
      setTone("danger");
      setResult(errorMessage(error));
      await onRefresh();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="panel p-3 task-card">
      <div className="d-flex justify-content-between align-items-start gap-3 mb-3">
        <div>
          <div className="fw-semibold">
            {task.name} · биржа {task.exchange}
          </div>
          <div className="muted small">ID {task.task_id}</div>
        </div>
        <span className="price-pill">{task.solved_by_me ? `+${task.my_solved_cost}` : task.cost}</span>
      </div>

      <div className="task-statement mb-3">{task.statement || "Условие пустое"}</div>

      <div className="d-flex flex-wrap gap-2 mb-3">
        <span className="badge text-bg-light">решений: {task.solves}</span>
        <span className="badge text-bg-light">рынок: {task.attempts} пос.</span>
        <span className="badge text-bg-light">ошибок рынка: {task.wrong_attempts}</span>
        <span className={`badge ${task.attempt_limit_reached ? "text-bg-danger" : "text-bg-light"}`}>посылок осталось: {task.attempts_left}</span>
        {task.solved_by_me ? (
          <span className="badge text-bg-success">
            решено на бирже {task.my_solved_exchange ?? task.exchange}
          </span>
        ) : null}
      </div>

      {task.solved_by_me && task.my_solved_exchange !== null && task.my_solved_exchange !== task.exchange ? (
        <div className="alert alert-success py-2 mb-3">
          Эта задача уже закрыта вашей командой на бирже {task.my_solved_exchange}.
        </div>
      ) : null}

      <Alert message={result} tone={tone} />

      <form onSubmit={submit} className="d-flex gap-2">
        <input
          className="form-control answer-input"
          value={solution}
          onChange={(event) => setSolution(event.target.value)}
          placeholder="Ответ"
          disabled={!task.can_submit || submitting}
          required
        />
        <LoadingButton loading={submitting} className="btn btn-primary" type="submit" disabled={!task.can_submit}>
          Сдать
        </LoadingButton>
      </form>
    </div>
  );
}
