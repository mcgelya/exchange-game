import type {
  GameInfo,
  LeaderboardResponse,
  RegisterResponse,
  StatusResponse,
  SubmissionAdmin,
  SubmitResponse,
  TaskBulkItem
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type RequestOptions = {
  token?: string;
  method?: string;
  body?: unknown;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};

  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`/api/backend${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    cache: "no-store"
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg || JSON.stringify(item)).join("; ")
          : `HTTP ${response.status}`;
    throw new ApiError(response.status, message);
  }

  return data as T;
}

export const api = {
  register: (payload: { game_id: string; team_name: string; members: string[] }) =>
    request<RegisterResponse>("/v1/register", { method: "POST", body: payload }),

  status: (token: string) => request<StatusResponse>("/v1/status", { token }),

  submit: (token: string, payload: { task: number; exchange: number; solution: string }) =>
    request<SubmitResponse>("/v1/submit", { token, method: "POST", body: payload }),

  leaderboard: (gameId: string) =>
    request<LeaderboardResponse>(`/v1/leaderboard/${encodeURIComponent(gameId)}`),

  adminGames: (adminToken: string) =>
    request<{ games: GameInfo[] }>("/v1/games", { token: adminToken }),

  adminCreateGame: (
    adminToken: string,
    payload: {
      exchanges: number;
      tasks: number;
      players: number;
      pool: string;
      duration_minutes?: number | null;
      base_cost?: number | null;
      cost_growth_per_minute?: number | null;
      exchange_step_percent?: number | null;
      solve_discount_percent?: number | null;
      wrong_attempt_limit?: number | null;
      wrong_attempt_growth_percent?: number | null;
    }
  ) => request<{ id: string; status: string }>("/v1/create", { token: adminToken, method: "POST", body: payload }),

  adminStart: (adminToken: string, gameId: string) =>
    request<{ id: string; status: string }>("/v1/start", {
      token: adminToken,
      method: "POST",
      body: { game_id: gameId }
    }),

  adminStop: (adminToken: string, gameId: string) =>
    request<{ id: string; status: string }>("/v1/stop", {
      token: adminToken,
      method: "POST",
      body: { game_id: gameId }
    }),

  adminAddPool: (adminToken: string, pool: string, tasks: TaskBulkItem[]) =>
    request<{ pool: string; created: number; updated: number }>("/v1/add_pool", {
      token: adminToken,
      method: "POST",
      body: { pool, tasks }
    }),

  adminAddTask: (
    adminToken: string,
    payload: { pool: string; name: string; statement: string; answer: string; base_cost?: number | null }
  ) => request<{ id: number; pool: string; name: string }>("/v1/add", { token: adminToken, method: "POST", body: payload }),

  adminSubmissions: (adminToken: string, gameId: string) =>
    request<{ game_id: string; submissions: SubmissionAdmin[] }>(
      `/v1/games/${encodeURIComponent(gameId)}/submissions`,
      { token: adminToken }
    ),

  adminBanSubmission: (adminToken: string, submissionId: number) =>
    request<{ id: number; banned: boolean; accepted: boolean; removed_solve: boolean }>(
      `/v1/submissions/${submissionId}/ban`,
      { token: adminToken, method: "POST" }
    )
};
