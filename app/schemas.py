from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class GameStatusEnum(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    STOPPED = "stopped"


class GameCreateRequest(BaseModel):
    exchanges: int = Field(..., ge=1, description="Number of exchanges to start")
    tasks: int = Field(..., ge=1, description="Number of tasks to generate")
    players: int = Field(..., ge=1, description="Number of participating players")
    pool: str = Field(..., min_length=1, description="Pool identifier")
    duration_minutes: int | None = Field(
        default=None, ge=1, description="Duration of the game in minutes (optional)"
    )
    base_cost: int | None = Field(
        default=None, ge=0, description="Base cost per task (defaults from settings)"
    )
    cost_growth_per_minute: int | None = Field(
        default=None, ge=0, description="Cost growth per minute"
    )
    exchange_step_percent: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Cost growth between neighboring exchanges",
    )
    solve_discount_percent: int | None = Field(
        default=None, ge=0, le=100, description="Cost discount after every solve"
    )
    wrong_attempt_limit: int | None = Field(
        default=None,
        ge=0,
        description="Max wrong attempts that can increase task cost",
    )
    wrong_attempt_growth_percent: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Cost growth for every counted wrong attempt",
    )


class GameCreateResponse(BaseModel):
    id: str = Field(..., description="Game identifier")
    status: GameStatusEnum = Field(..., description="Game status")


class GameStartRequest(BaseModel):
    game_id: str = Field(..., description="Game identifier to start")


class GameStartResponse(BaseModel):
    id: str = Field(..., description="Game identifier")
    status: GameStatusEnum = Field(..., description="Game status")


class GameStopRequest(BaseModel):
    game_id: str = Field(..., description="Game identifier to stop")


class GameStopResponse(BaseModel):
    id: str = Field(..., description="Game identifier")
    status: GameStatusEnum = Field(..., description="Game status")


class GameInfo(BaseModel):
    id: str
    status: GameStatusEnum
    pool: str
    exchanges: int
    tasks: int
    players: int
    registered_players: int
    duration_minutes: int | None = None
    base_cost: int
    cost_growth_per_minute: int
    exchange_step_percent: int
    solve_discount_percent: int
    wrong_attempt_limit: int
    wrong_attempt_growth_percent: int
    created_at: datetime | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    server_time: datetime | None = None


class GameListResponse(BaseModel):
    games: list[GameInfo]


class RegisterRequest(BaseModel):
    game_id: str = Field(..., description="Target game identifier")
    team_name: str | None = Field(
        default=None, min_length=1, description="Team display name"
    )
    members: list[str] = Field(default_factory=list, description="Team members")


class RegisterResponse(BaseModel):
    token: str = Field(..., description="Personal token for this game")
    player_id: int
    team_name: str
    members: list[str]


class PlayerInfo(BaseModel):
    id: int
    team_name: str
    members: list[str]


class TaskStatus(BaseModel):
    task_id: int
    name: str
    statement: str
    exchange: int
    base_cost: int
    cost: int
    solved_by_me: bool
    my_solved_cost: int | None = None
    can_submit: bool
    attempts: int
    my_attempts: int
    wrong_attempts: int
    wrong_attempts_left: int
    wrong_limit_reached: bool
    solves: int

    model_config = ConfigDict(from_attributes=True)


class StatusResponse(BaseModel):
    game_id: str
    game: GameInfo
    player: PlayerInfo
    tasks: list[TaskStatus]


class SubmitRequest(BaseModel):
    task: int = Field(..., description="Task identifier")
    solution: str = Field(..., min_length=1, description="Proposed answer")
    exchange: int = Field(..., ge=1, description="Exchange number")


class SubmitResponse(BaseModel):
    accepted: bool
    task_id: int
    exchange: int
    cost: int
    solved_by_me: bool
    attempts: int
    wrong_attempts: int
    solves: int


class TaskAddRequest(BaseModel):
    pool: str = Field(..., min_length=1, description="Pool name/slug")
    name: str = Field(..., min_length=1, description="Task name")
    statement: str = Field(default="", description="Task statement")
    answer: str = Field(..., min_length=1, description="Correct answer")
    base_cost: int | None = Field(default=None, ge=0, description="Task base cost")


class TaskAddResponse(BaseModel):
    id: int
    pool: str
    name: str
    statement: str
    base_cost: int


class TaskBulkItem(BaseModel):
    name: str = Field(..., min_length=1, description="Task name")
    statement: str = Field(default="", description="Task statement")
    answer: str = Field(..., min_length=1, description="Correct answer")
    base_cost: int | None = Field(default=None, ge=0, description="Task base cost")


class TaskBulkAddRequest(BaseModel):
    pool: str = Field(..., min_length=1, description="Pool name/slug")
    tasks: list[TaskBulkItem] = Field(..., min_length=1)


class TaskBulkAddResponse(BaseModel):
    pool: str
    created: int
    updated: int
    tasks: list[TaskAddResponse]


class LeaderboardPlayer(BaseModel):
    rank: int
    player_id: int
    team_name: str
    members: list[str]
    score: int
    solves: int
    attempts: int
    wrong_attempts: int
    last_solve_at: datetime | None = None


class LeaderboardSolve(BaseModel):
    player_id: int
    team_name: str
    cost: int
    solved_at: datetime


class LeaderboardTask(BaseModel):
    task_id: int
    name: str
    statement: str
    exchange: int
    base_cost: int
    current_cost: int
    solves: int
    attempts: int
    wrong_attempts: int
    solved_by: list[LeaderboardSolve]


class LeaderboardResponse(BaseModel):
    game_id: str
    status: GameStatusEnum
    players: list[LeaderboardPlayer]
    tasks: list[LeaderboardTask]


class SubmissionAdmin(BaseModel):
    id: int
    game_id: str
    player_id: int
    team_name: str
    task_id: int
    task_name: str
    exchange: int
    submitted_answer: str
    accepted: bool
    cost: int
    banned: bool
    created_at: datetime | None = None


class SubmissionListResponse(BaseModel):
    game_id: str
    submissions: list[SubmissionAdmin]


class SubmissionBanResponse(BaseModel):
    id: int
    banned: bool
    accepted: bool
    removed_solve: bool
