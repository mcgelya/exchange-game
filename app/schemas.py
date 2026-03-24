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


class RegisterRequest(BaseModel):
    game_id: str = Field(..., description="Target game identifier")


class RegisterResponse(BaseModel):
    token: str = Field(..., description="Personal token for this game")


class TaskStatus(BaseModel):
    task_id: int
    name: str
    exchange: int
    base_cost: int
    cost: int
    solved_by_me: bool
    my_solved_cost: int | None = None
    attempts: int
    my_attempts: int
    wrong_attempts: int
    solves: int

    model_config = ConfigDict(from_attributes=True)


class StatusResponse(BaseModel):
    game_id: str
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
    answer: str = Field(..., min_length=1, description="Correct answer")
    base_cost: int | None = Field(default=None, ge=0, description="Task base cost")


class TaskAddResponse(BaseModel):
    id: int
    pool: str
    name: str
    base_cost: int


class TaskBulkItem(BaseModel):
    name: str = Field(..., min_length=1, description="Task name")
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
    score: int
    solves: int
    attempts: int
    wrong_attempts: int
    last_solve_at: datetime | None = None


class LeaderboardSolve(BaseModel):
    player_id: int
    cost: int
    solved_at: datetime


class LeaderboardTask(BaseModel):
    task_id: int
    name: str
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
