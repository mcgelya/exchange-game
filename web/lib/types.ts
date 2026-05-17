export type GameStatus = "created" | "active" | "stopped";

export type GameInfo = {
  id: string;
  status: GameStatus;
  pool: string;
  exchanges: number;
  tasks: number;
  players: number;
  registered_players: number;
  duration_minutes: number | null;
  base_cost: number;
  cost_growth_per_minute: number;
  exchange_step_percent: number;
  solve_discount_percent: number;
  attempt_limit: number;
  wrong_attempt_growth_percent: number;
  created_at: string | null;
  started_at: string | null;
  stopped_at: string | null;
  server_time: string | null;
};

export type PlayerInfo = {
  id: number;
  team_name: string;
  members: string[];
};

export type TaskStatus = {
  task_id: number;
  name: string;
  statement: string;
  exchange: number;
  base_cost: number;
  cost: number;
  solved_by_me: boolean;
  my_solved_exchange: number | null;
  my_solved_cost: number | null;
  can_submit: boolean;
  attempts: number;
  my_attempts: number;
  wrong_attempts: number;
  attempts_left: number;
  attempt_limit_reached: boolean;
  solves: number;
};

export type StatusResponse = {
  game_id: string;
  game: GameInfo;
  player: PlayerInfo;
  tasks: TaskStatus[];
};

export type RegisterResponse = {
  token: string;
  player_id: number;
  team_name: string;
  members: string[];
};

export type SubmitResponse = {
  accepted: boolean;
  task_id: number;
  exchange: number;
  cost: number;
  solved_by_me: boolean;
  solved_exchange: number | null;
  attempts: number;
  attempts_left: number;
  attempt_limit_reached: boolean;
  wrong_attempts: number;
  solves: number;
};

export type LeaderboardPlayer = {
  rank: number;
  player_id: number;
  team_name: string;
  members: string[];
  score: number;
  solves: number;
  attempts: number;
  wrong_attempts: number;
  last_solve_at: string | null;
};

export type LeaderboardSolve = {
  player_id: number;
  team_name: string;
  cost: number;
  solved_at: string;
};

export type LeaderboardTask = {
  task_id: number;
  name: string;
  statement: string;
  exchange: number;
  base_cost: number;
  current_cost: number;
  solves: number;
  attempts: number;
  wrong_attempts: number;
  solved_by: LeaderboardSolve[];
};

export type LeaderboardResponse = {
  game_id: string;
  status: GameStatus;
  players: LeaderboardPlayer[];
  tasks: LeaderboardTask[];
};

export type SubmissionAdmin = {
  id: number;
  game_id: string;
  player_id: number;
  team_name: string;
  task_id: number;
  task_name: string;
  exchange: number;
  submitted_answer: string;
  accepted: boolean;
  cost: number;
  banned: boolean;
  created_at: string | null;
};

export type TaskBulkItem = {
  name: string;
  statement: string;
  answer: string;
  accepted_answers?: string[];
  base_cost?: number | null;
};
