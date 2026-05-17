"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Alert } from "@/components/Alert";
import { LoadingButton } from "@/components/LoadingButton";
import { api, ApiError } from "@/lib/api";
import { formatDate, statusClass, statusLabel } from "@/lib/format";
import type { GameInfo, LeaderboardResponse, SubmissionAdmin, TaskBulkItem } from "@/lib/types";

const ADMIN_TOKEN_KEY = "exchange-game-admin-token";

const bulkExample = JSON.stringify(
  [
    {
      name: "A",
      statement: "Find 40 + 2.",
      answer: "42",
      accepted_answers: ["0042"],
      base_cost: 100
    },
    {
      name: "B",
      statement: "Find 3 + 4.",
      answer: "7",
      accepted_answers: [],
      base_cost: 120
    }
  ],
  null,
  2
);

function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Неизвестная ошибка";
}

function requiredNumber(data: FormData, key: string) {
  const value = String(data.get(key) || "").trim();
  if (!value) throw new Error(`Поле ${key} обязательно`);
  return Number(value);
}

function optionalNumber(data: FormData, key: string) {
  const value = String(data.get(key) || "").trim();
  return value ? Number(value) : null;
}

function splitAcceptedAnswers(value: FormDataEntryValue | null) {
  return String(value || "")
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function AdminPage() {
  const [adminToken, setAdminToken] = useState("");
  const [games, setGames] = useState<GameInfo[]>([]);
  const [selectedGameId, setSelectedGameId] = useState("");
  const [leaderboard, setLeaderboard] = useState<LeaderboardResponse | null>(null);
  const [submissions, setSubmissions] = useState<SubmissionAdmin[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<string | null>(null);
  const [bulkPool, setBulkPool] = useState("demo");
  const [bulkTasks, setBulkTasks] = useState(bulkExample);

  const selectedGame = useMemo(
    () => games.find((game) => game.id === selectedGameId) || null,
    [games, selectedGameId]
  );

  const loadGames = useCallback(
    async (token = adminToken) => {
      if (!token) return;
      setLoading(true);
      try {
        const response = await api.adminGames(token);
        setGames(response.games);
        setSelectedGameId((current) => current || response.games[0]?.id || "");
        setMessage(null);
      } catch (error) {
        setMessage(errorMessage(error));
      } finally {
        setLoading(false);
      }
    },
    [adminToken]
  );

  const loadSelectedDetails = useCallback(
    async (gameId = selectedGameId) => {
      if (!gameId) return;
      try {
        const [nextLeaderboard, nextSubmissions] = await Promise.all([
          api.leaderboard(gameId),
          adminToken ? api.adminSubmissions(adminToken, gameId) : Promise.resolve({ submissions: [] })
        ]);
        setLeaderboard(nextLeaderboard);
        setSubmissions(nextSubmissions.submissions);
      } catch (error) {
        setMessage(errorMessage(error));
      }
    },
    [adminToken, selectedGameId]
  );

  useEffect(() => {
    const stored = window.localStorage.getItem(ADMIN_TOKEN_KEY) || "";
    if (stored) {
      setAdminToken(stored);
      void loadGames(stored);
    }
  }, [loadGames]);

  useEffect(() => {
    if (selectedGameId) {
      void loadSelectedDetails(selectedGameId);
    }
  }, [loadSelectedDetails, selectedGameId]);

  async function saveToken(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = adminToken.trim();
    window.localStorage.setItem(ADMIN_TOKEN_KEY, token);
    setSuccess("Админский токен сохранен");
    await loadGames(token);
  }

  async function createGame(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAction("create");
    setMessage(null);
    setSuccess(null);

    try {
      const data = new FormData(event.currentTarget);
      const response = await api.adminCreateGame(adminToken, {
        exchanges: requiredNumber(data, "exchanges"),
        tasks: requiredNumber(data, "tasks"),
        players: requiredNumber(data, "players"),
        pool: String(data.get("pool") || "").trim(),
        duration_minutes: optionalNumber(data, "duration_minutes"),
        base_cost: optionalNumber(data, "base_cost"),
        cost_growth_per_minute: optionalNumber(data, "cost_growth_per_minute"),
        exchange_step_percent: optionalNumber(data, "exchange_step_percent"),
        solve_discount_percent: optionalNumber(data, "solve_discount_percent"),
        attempt_limit: optionalNumber(data, "attempt_limit"),
        wrong_attempt_growth_percent: optionalNumber(data, "wrong_attempt_growth_percent")
      });
      setSuccess(`Игра ${response.id} создана`);
      setSelectedGameId(response.id);
      await loadGames();
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setAction(null);
    }
  }

  async function addTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setAction("add-task");
    setMessage(null);
    setSuccess(null);

    try {
      const data = new FormData(form);
      const response = await api.adminAddTask(adminToken, {
        pool: String(data.get("pool") || "").trim(),
        name: String(data.get("name") || "").trim(),
        statement: String(data.get("statement") || ""),
        answer: String(data.get("answer") || "").trim(),
        accepted_answers: splitAcceptedAnswers(data.get("accepted_answers")),
        base_cost: optionalNumber(data, "base_cost")
      });
      setSuccess(`Задача ${response.name} сохранена в пуле ${response.pool}`);
      form.reset();
      await loadGames();
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setAction(null);
    }
  }

  async function addPool(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAction("add-pool");
    setMessage(null);
    setSuccess(null);

    try {
      const parsed = JSON.parse(bulkTasks) as TaskBulkItem[];
      if (!Array.isArray(parsed)) {
        throw new Error("JSON должен быть массивом задач");
      }
      const response = await api.adminAddPool(adminToken, bulkPool.trim(), parsed);
      setSuccess(`Пул ${response.pool}: создано ${response.created}, обновлено ${response.updated}`);
      await loadGames();
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setAction(null);
    }
  }

  async function changeGameStatus(kind: "start" | "stop", gameId: string) {
    setAction(`${kind}-${gameId}`);
    setMessage(null);
    setSuccess(null);
    try {
      const response = kind === "start" ? await api.adminStart(adminToken, gameId) : await api.adminStop(adminToken, gameId);
      setSuccess(`Игра ${response.id}: ${statusLabel(response.status)}`);
      await loadGames();
      await loadSelectedDetails(gameId);
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setAction(null);
    }
  }

  async function banSubmission(submissionId: number) {
    setAction(`ban-${submissionId}`);
    setMessage(null);
    setSuccess(null);
    try {
      const response = await api.adminBanSubmission(adminToken, submissionId);
      setSuccess(response.removed_solve ? "Посылка забанена, решение снято" : "Посылка забанена");
      await loadSelectedDetails(selectedGameId);
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setAction(null);
    }
  }

  return (
    <div className="vstack gap-4">
      <div className="panel p-4">
        <div className="d-flex flex-wrap justify-content-between align-items-start gap-3">
          <div>
            <h1 className="h3 mb-2">Админка</h1>
            <p className="muted mb-0">Игры, пулы задач, старт/стоп и модерация посылок.</p>
          </div>
          <form onSubmit={saveToken} className="d-flex gap-2">
            <input className="form-control" value={adminToken} onChange={(event) => setAdminToken(event.target.value)} placeholder="API key" />
            <LoadingButton loading={loading} className="btn btn-dark" type="submit">
              Войти
            </LoadingButton>
          </form>
        </div>
      </div>

      <Alert message={message} />
      <Alert message={success} tone="success" />

      <div className="row g-4">
        <div className="col-xl-7">
          <GamesPanel
            games={games}
            selectedGameId={selectedGameId}
            action={action}
            onSelect={setSelectedGameId}
            onRefresh={() => loadGames()}
            onStatus={changeGameStatus}
          />
        </div>
        <div className="col-xl-5">
          <CreateGamePanel action={action} onCreate={createGame} />
        </div>
      </div>

      <div className="row g-4">
        <div className="col-xl-5">
          <TaskPanel action={action} bulkPool={bulkPool} bulkTasks={bulkTasks} onBulkPool={setBulkPool} onBulkTasks={setBulkTasks} onAddTask={addTask} onAddPool={addPool} />
        </div>
        <div className="col-xl-7">
          <SelectedGamePanel game={selectedGame} leaderboard={leaderboard} submissions={submissions} action={action} onRefresh={() => loadSelectedDetails(selectedGameId)} onBan={banSubmission} />
        </div>
      </div>
    </div>
  );
}

function GamesPanel({
  games,
  selectedGameId,
  action,
  onSelect,
  onRefresh,
  onStatus
}: {
  games: GameInfo[];
  selectedGameId: string;
  action: string | null;
  onSelect: (id: string) => void;
  onRefresh: () => Promise<void>;
  onStatus: (kind: "start" | "stop", gameId: string) => Promise<void>;
}) {
  return (
    <div className="panel p-0 overflow-hidden">
      <div className="p-3 border-bottom d-flex justify-content-between align-items-center">
        <h2 className="h5 mb-0">Игры</h2>
        <button className="btn btn-sm btn-outline-primary" type="button" onClick={() => void onRefresh()}>
          Обновить
        </button>
      </div>
      <div className="table-responsive">
        <table className="table table-hover align-middle mb-0">
          <thead className="table-light">
            <tr>
              <th>ID</th>
              <th>Статус</th>
              <th>Пул</th>
              <th>Команды</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {games.map((game) => (
              <tr className={game.id === selectedGameId ? "table-primary" : ""} key={game.id}>
                <td>
                  <button className="btn btn-link p-0 fw-semibold" type="button" onClick={() => onSelect(game.id)}>
                    {game.id}
                  </button>
                  <div className="muted small">{formatDate(game.started_at || game.created_at)}</div>
                </td>
                <td>
                  <span className={`badge ${statusClass(game.status)}`}>{statusLabel(game.status)}</span>
                </td>
                <td>
                  {game.pool}
                  <div className="muted small">
                    {game.tasks} задач · {game.exchanges} бирж
                  </div>
                </td>
                <td>
                  {game.registered_players}/{game.players}
                </td>
                <td>
                  <div className="d-flex gap-2">
                    <LoadingButton
                      loading={action === `start-${game.id}`}
                      className="btn btn-sm btn-outline-success"
                      type="button"
                      disabled={game.status !== "created"}
                      onClick={() => void onStatus("start", game.id)}
                    >
                      Старт
                    </LoadingButton>
                    <LoadingButton
                      loading={action === `stop-${game.id}`}
                      className="btn btn-sm btn-outline-danger"
                      type="button"
                      disabled={game.status === "stopped"}
                      onClick={() => void onStatus("stop", game.id)}
                    >
                      Стоп
                    </LoadingButton>
                  </div>
                </td>
              </tr>
            ))}
            {!games.length ? (
              <tr>
                <td colSpan={5} className="text-center muted py-4">
                  Список пуст или токен не указан
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CreateGamePanel({ action, onCreate }: { action: string | null; onCreate: (event: FormEvent<HTMLFormElement>) => Promise<void> }) {
  return (
    <div className="panel p-4">
      <h2 className="h5 mb-3">Создать игру</h2>
      <form onSubmit={onCreate} className="row g-3">
        <div className="col-12">
          <label className="form-label">Пул</label>
          <input className="form-control" name="pool" defaultValue="demo" required />
        </div>
        <div className="col-4">
          <label className="form-label">Биржи</label>
          <input className="form-control" name="exchanges" type="number" min={1} defaultValue={2} required />
        </div>
        <div className="col-4">
          <label className="form-label">Задачи</label>
          <input className="form-control" name="tasks" type="number" min={1} defaultValue={10} required />
        </div>
        <div className="col-4">
          <label className="form-label">Команды</label>
          <input className="form-control" name="players" type="number" min={1} defaultValue={6} required />
        </div>
        <div className="col-6">
          <label className="form-label">Минуты</label>
          <input className="form-control" name="duration_minutes" type="number" min={1} placeholder="90" />
        </div>
        <div className="col-6">
          <label className="form-label">База</label>
          <input className="form-control" name="base_cost" type="number" min={0} placeholder="100" />
        </div>
        <div className="col-6">
          <label className="form-label">Рост/мин</label>
          <input className="form-control" name="cost_growth_per_minute" type="number" min={0} placeholder="5" />
        </div>
        <div className="col-6">
          <label className="form-label">Шаг бирж, %</label>
          <input className="form-control" name="exchange_step_percent" type="number" min={0} max={100} placeholder="10" />
        </div>
        <div className="col-6">
          <label className="form-label">Скидка решения, %</label>
          <input className="form-control" name="solve_discount_percent" type="number" min={0} max={100} placeholder="10" />
        </div>
        <div className="col-6">
          <label className="form-label">Лимит посылок</label>
          <input className="form-control" name="attempt_limit" type="number" min={0} placeholder="6" />
        </div>
        <div className="col-12">
          <label className="form-label">Рост за ошибку, %</label>
          <input className="form-control" name="wrong_attempt_growth_percent" type="number" min={0} max={100} placeholder="3" />
        </div>
        <div className="col-12">
          <LoadingButton loading={action === "create"} className="btn btn-primary w-100" type="submit">
            Создать
          </LoadingButton>
        </div>
      </form>
    </div>
  );
}

function TaskPanel({
  action,
  bulkPool,
  bulkTasks,
  onBulkPool,
  onBulkTasks,
  onAddTask,
  onAddPool
}: {
  action: string | null;
  bulkPool: string;
  bulkTasks: string;
  onBulkPool: (value: string) => void;
  onBulkTasks: (value: string) => void;
  onAddTask: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onAddPool: (event: FormEvent<HTMLFormElement>) => Promise<void>;
}) {
  return (
    <div className="vstack gap-4">
      <div className="panel p-4">
        <h2 className="h5 mb-3">Одна задача</h2>
        <form onSubmit={onAddTask} className="vstack gap-3">
          <div className="row g-3">
            <div className="col-6">
              <label className="form-label">Пул</label>
              <input className="form-control" name="pool" defaultValue="demo" required />
            </div>
            <div className="col-6">
              <label className="form-label">Имя</label>
              <input className="form-control" name="name" placeholder="A" required />
            </div>
          </div>
          <div>
            <label className="form-label">Условие</label>
            <textarea className="form-control" name="statement" rows={3} />
          </div>
          <div className="row g-3">
            <div className="col-8">
              <label className="form-label">Ответ</label>
              <input className="form-control" name="answer" required />
            </div>
            <div className="col-4">
              <label className="form-label">Цена</label>
              <input className="form-control" name="base_cost" type="number" min={0} />
            </div>
          </div>
          <div>
            <label className="form-label">Дополнительные верные ответы</label>
            <textarea
              className="form-control"
              name="accepted_answers"
              rows={3}
              placeholder="0042, 42.0"
            />
            <div className="form-text">Через запятую или с новой строки.</div>
          </div>
          <LoadingButton loading={action === "add-task"} className="btn btn-outline-primary" type="submit">
            Сохранить задачу
          </LoadingButton>
        </form>
      </div>

      <div className="panel p-4">
        <h2 className="h5 mb-3">Загрузить пул</h2>
        <form onSubmit={onAddPool} className="vstack gap-3">
          <div>
            <label className="form-label">Пул</label>
            <input className="form-control" value={bulkPool} onChange={(event) => onBulkPool(event.target.value)} required />
          </div>
          <div>
            <label className="form-label">JSON задач</label>
            <textarea
              className="form-control code-textarea code-textarea-lg"
              value={bulkTasks}
              onChange={(event) => onBulkTasks(event.target.value)}
              rows={16}
              spellCheck={false}
              required
            />
            <div className="form-text">
              Массив задач JSON. Поддерживаются поля name, statement, answer, accepted_answers, base_cost.
            </div>
          </div>
          <LoadingButton loading={action === "add-pool"} className="btn btn-primary" type="submit">
            Загрузить
          </LoadingButton>
        </form>
      </div>
    </div>
  );
}

function SelectedGamePanel({
  game,
  leaderboard,
  submissions,
  action,
  onRefresh,
  onBan
}: {
  game: GameInfo | null;
  leaderboard: LeaderboardResponse | null;
  submissions: SubmissionAdmin[];
  action: string | null;
  onRefresh: () => Promise<void>;
  onBan: (submissionId: number) => Promise<void>;
}) {
  return (
    <div className="panel p-0 overflow-hidden">
      <div className="p-3 border-bottom d-flex flex-wrap justify-content-between align-items-center gap-2">
        <div>
          <h2 className="h5 mb-1">{game ? `Игра ${game.id}` : "Игра не выбрана"}</h2>
          {game ? (
            <div className="muted small">
              {statusLabel(game.status)} · {game.registered_players}/{game.players} команд · старт {formatDate(game.started_at)}
            </div>
          ) : null}
        </div>
        <div className="d-flex gap-2">
          {game ? (
            <Link className="btn btn-sm btn-outline-primary" href={`/leaderboard/${game.id}`}>
              Публичный рейтинг
            </Link>
          ) : null}
          <button className="btn btn-sm btn-outline-secondary" type="button" onClick={() => void onRefresh()} disabled={!game}>
            Обновить
          </button>
        </div>
      </div>

      {game ? (
        <div className="p-3 vstack gap-4">
          <div className="row g-3">
            <div className="col-6 col-md-3">
              <div className="metric">
                <div className="muted small">База</div>
                <div className="h5 mb-0">{game.base_cost}</div>
              </div>
            </div>
            <div className="col-6 col-md-3">
              <div className="metric">
                <div className="muted small">Рост/мин</div>
                <div className="h5 mb-0">{game.cost_growth_per_minute}</div>
              </div>
            </div>
            <div className="col-6 col-md-3">
              <div className="metric">
                <div className="muted small">Скидка</div>
                <div className="h5 mb-0">{game.solve_discount_percent}%</div>
              </div>
            </div>
            <div className="col-6 col-md-3">
              <div className="metric">
                <div className="muted small">Лимит посылок</div>
                <div className="h5 mb-0">{game.attempt_limit}</div>
              </div>
            </div>
          </div>

          <div>
            <h3 className="h6 mb-3">Топ команд</h3>
            <div className="table-responsive">
              <table className="table table-sm align-middle mb-0">
                <tbody>
                  {(leaderboard?.players || []).slice(0, 5).map((player) => (
                    <tr key={player.player_id}>
                      <td className="fw-semibold">#{player.rank}</td>
                      <td>{player.team_name}</td>
                      <td className="text-end">{player.score}</td>
                      <td className="text-end muted">{player.solves} реш.</td>
                    </tr>
                  ))}
                  {!leaderboard?.players.length ? (
                    <tr>
                      <td className="muted py-3">Пока нет команд</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h3 className="h6 mb-3">Посылки</h3>
            <div className="table-responsive">
              <table className="table table-sm table-hover align-middle mb-0">
                <thead className="table-light">
                  <tr>
                    <th>ID</th>
                    <th>Команда</th>
                    <th>Задача</th>
                    <th>Ответ</th>
                    <th>Итог</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {submissions
                    .slice()
                    .reverse()
                    .slice(0, 80)
                    .map((submission) => (
                      <tr className={submission.banned ? "table-secondary" : ""} key={submission.id}>
                        <td>
                          {submission.id}
                          <div className="muted small">{formatDate(submission.created_at)}</div>
                        </td>
                        <td>{submission.team_name}</td>
                        <td>
                          {submission.task_name}
                          <div className="muted small">биржа {submission.exchange}</div>
                        </td>
                        <td className="text-break">{submission.submitted_answer}</td>
                        <td>
                          {submission.accepted ? <span className="badge text-bg-success">+{submission.cost}</span> : <span className="badge text-bg-warning">неверно</span>}
                          {submission.banned ? <span className="badge text-bg-secondary ms-1">бан</span> : null}
                        </td>
                        <td className="text-end">
                          <LoadingButton
                            loading={action === `ban-${submission.id}`}
                            className="btn btn-sm btn-outline-danger"
                            type="button"
                            disabled={submission.banned}
                            onClick={() => void onBan(submission.id)}
                          >
                            Бан
                          </LoadingButton>
                        </td>
                      </tr>
                    ))}
                  {!submissions.length ? (
                    <tr>
                      <td colSpan={6} className="text-center muted py-4">
                        Посылок пока нет
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-5 text-center muted">Выбери игру из списка</div>
      )}
    </div>
  );
}
