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
    submit_penalty: int | None = Field(
        default=None, ge=0, description="Penalty per submit attempt"
    )
    solve_bonus: int | None = Field(
        default=None, ge=0, description="Bonus (cost reduction) on solve"
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
    exchange: int
    cost: int
    solved: bool
    solved_by_me: bool
    attempts: int
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
    solved: bool
    attempts: int


class TaskAddRequest(BaseModel):
    pool: str = Field(..., min_length=1, description="Pool name/slug")
    name: str = Field(..., min_length=1, description="Task name")
    answer: str = Field(..., min_length=1, description="Correct answer")


class TaskAddResponse(BaseModel):
    id: int
    pool: str
    name: str
