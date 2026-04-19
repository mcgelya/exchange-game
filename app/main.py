from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import secrets
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Integer, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas
from app.config import get_settings
from app.db import Base, engine, get_session
from app.utils import pick

admin_scheme = HTTPBearer(auto_error=True)
player_scheme = HTTPBearer(auto_error=True)
settings = get_settings()
TaskKey = tuple[int, int]


def game_code() -> str:
    return f"G-{uuid4().hex[:8].upper()}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="exchange-game API", lifespan=lifespan)


async def require_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(admin_scheme),
):
    if credentials.credentials != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials


async def require_player(
    credentials: HTTPAuthorizationCredentials = Depends(player_scheme),
    session: AsyncSession = Depends(get_session),
):
    token = credentials.credentials
    player = await session.scalar(
        select(models.Player).where(models.Player.token == token)
    )
    if not player:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or unknown token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    game = await session.get(models.Game, player.game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game for this token not found",
        )
    return player, game, session


def as_utc(value: datetime | None) -> datetime | None:
    if value and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def normalize_answer(value: str) -> str:
    return value.strip().lower()


def encode_members(members: list[str]) -> str:
    cleaned = [member.strip() for member in members if member.strip()]
    return json.dumps(cleaned, ensure_ascii=False)


def decode_members(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(member) for member in parsed]


def player_info(player: models.Player) -> schemas.PlayerInfo:
    return schemas.PlayerInfo(
        id=player.id,
        team_name=player.team_name,
        members=decode_members(player.members),
    )


def exchange_multiplier(exchange: int, exchange_step_percent: int) -> float:
    return 1 + (exchange_step_percent / 100) * (exchange - 1)


def compute_cost(
    task: models.Task,
    game: models.Game,
    exchange: int,
    solve_count: int,
    wrong_attempt_count: int = 0,
    *,
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(timezone.utc)
    start_time = as_utc(game.started_at) or as_utc(game.created_at) or now
    end_time = as_utc(game.stopped_at) or now
    elapsed_minutes = max(0, int((end_time - start_time).total_seconds() // 60))

    base_cost = task.base_cost if task.base_cost is not None else game.base_cost
    grown_cost = (
        base_cost * exchange_multiplier(exchange, game.exchange_step_percent)
    ) + (game.cost_growth_per_minute * elapsed_minutes)
    wrong_multiplier = (
        1 + (game.wrong_attempt_growth_percent / 100) * wrong_attempt_count
    )
    discount = max(0, 1 - game.solve_discount_percent / 100)
    cost = grown_cost * wrong_multiplier * (discount**solve_count)
    return max(1, int(round(cost)))


@dataclass(frozen=True)
class TaskCounters:
    solves: dict[TaskKey, int]
    attempts: dict[TaskKey, int]
    wrong_attempts: dict[TaskKey, int]

    def solve_count(self, key: TaskKey) -> int:
        return self.solves.get(key, 0)

    def attempt_count(self, key: TaskKey) -> int:
        return self.attempts.get(key, 0)

    def wrong_count(self, key: TaskKey) -> int:
        return self.wrong_attempts.get(key, 0)

    def cost(
        self,
        task: models.Task,
        game: models.Game,
        exchange: int,
        *,
        now: datetime | None = None,
    ) -> int:
        key = (task.id, exchange)
        return compute_cost(
            task,
            game,
            exchange,
            self.solve_count(key),
            self.wrong_count(key),
            now=now,
        )


async def maybe_stop_expired(game: models.Game, session: AsyncSession) -> models.Game:
    if (
        game.status == models.GameStatus.ACTIVE
        and game.started_at
        and game.duration_minutes
    ):
        now = datetime.now(timezone.utc)
        start_time = as_utc(game.started_at) or now
        if now >= start_time + timedelta(minutes=game.duration_minutes):
            game.status = models.GameStatus.STOPPED
            game.stopped_at = now
            await session.commit()
    return game


async def get_game_tasks(game: models.Game, session: AsyncSession) -> list[models.Task]:
    result = await session.execute(
        select(models.Task)
        .where(models.Task.pool == game.pool)
        .order_by(models.Task.id)
        .limit(game.tasks)
    )
    return list(result.scalars().all())


async def registered_player_count(game_id: str, session: AsyncSession) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(models.Player)
            .where(models.Player.game_id == game_id)
        )
        or 0
    )


async def game_info(game: models.Game, session: AsyncSession) -> schemas.GameInfo:
    return schemas.GameInfo(
        id=game.id,
        status=game.status,
        pool=game.pool,
        exchanges=game.exchanges,
        tasks=game.tasks,
        players=game.players,
        registered_players=await registered_player_count(game.id, session),
        duration_minutes=game.duration_minutes,
        base_cost=game.base_cost,
        cost_growth_per_minute=game.cost_growth_per_minute,
        exchange_step_percent=game.exchange_step_percent,
        solve_discount_percent=game.solve_discount_percent,
        wrong_attempt_limit=game.wrong_attempt_limit,
        wrong_attempt_growth_percent=game.wrong_attempt_growth_percent,
        created_at=game.created_at,
        started_at=game.started_at,
        stopped_at=game.stopped_at,
        server_time=datetime.now(timezone.utc),
    )


async def get_solve_counts(game_id: str, session: AsyncSession) -> dict[TaskKey, int]:
    rows = await session.execute(
        select(
            models.PlayerSolved.task_id,
            models.PlayerSolved.exchange,
            func.count(models.PlayerSolved.id),
        )
        .where(models.PlayerSolved.game_id == game_id)
        .group_by(models.PlayerSolved.task_id, models.PlayerSolved.exchange)
    )
    return {(task_id, exchange): count for task_id, exchange, count in rows.all()}


async def get_attempt_counts(game_id: str, session: AsyncSession) -> dict[TaskKey, int]:
    rows = await session.execute(
        select(
            models.Submission.task_id,
            models.Submission.exchange,
            func.count(models.Submission.id),
        )
        .where(
            models.Submission.game_id == game_id,
            models.Submission.banned.is_(False),
        )
        .group_by(models.Submission.task_id, models.Submission.exchange)
    )
    return {(task_id, exchange): count for task_id, exchange, count in rows.all()}


async def get_wrong_attempt_counts(
    game_id: str, session: AsyncSession
) -> dict[TaskKey, int]:
    rows = await session.execute(
        select(
            models.Submission.task_id,
            models.Submission.exchange,
            func.count(models.Submission.id),
        )
        .where(
            models.Submission.game_id == game_id,
            models.Submission.accepted.is_(False),
            models.Submission.banned.is_(False),
        )
        .group_by(models.Submission.task_id, models.Submission.exchange)
    )
    return {(task_id, exchange): count for task_id, exchange, count in rows.all()}


async def get_task_counters(game_id: str, session: AsyncSession) -> TaskCounters:
    return TaskCounters(
        solves=await get_solve_counts(game_id, session),
        attempts=await get_attempt_counts(game_id, session),
        wrong_attempts=await get_wrong_attempt_counts(game_id, session),
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/v1/games", response_model=schemas.GameListResponse)
async def list_games(
    _auth=Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(models.Game).order_by(models.Game.created_at))
    games = [await game_info(game, session) for game in result.scalars().all()]
    return schemas.GameListResponse(games=games)


@app.get("/v1/games/{game_id}", response_model=schemas.GameInfo)
async def get_game(
    game_id: str,
    _auth=Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    game = await session.get(models.Game, game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Game not found"
        )
    game = await maybe_stop_expired(game, session)
    return await game_info(game, session)


@app.post(
    "/v1/create",
    response_model=schemas.GameCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_game(
    payload: schemas.GameCreateRequest,
    _auth=Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    game = models.Game(
        id=game_code(),
        status=models.GameStatus.CREATED,
        exchanges=payload.exchanges,
        tasks=payload.tasks,
        players=payload.players,
        pool=payload.pool,
        base_cost=pick(payload.base_cost, settings.base_task_cost),
        cost_growth_per_minute=pick(
            payload.cost_growth_per_minute, settings.cost_growth_per_minute
        ),
        exchange_step_percent=pick(
            payload.exchange_step_percent, settings.exchange_step_percent
        ),
        solve_discount_percent=pick(
            payload.solve_discount_percent, settings.solve_discount_percent
        ),
        wrong_attempt_limit=pick(
            payload.wrong_attempt_limit, settings.wrong_attempt_limit
        ),
        wrong_attempt_growth_percent=pick(
            payload.wrong_attempt_growth_percent,
            settings.wrong_attempt_growth_percent,
        ),
        duration_minutes=payload.duration_minutes,
    )
    session.add(game)
    await session.commit()

    return schemas.GameCreateResponse(id=game.id, status=game.status)


@app.post(
    "/v1/start",
    response_model=schemas.GameStartResponse,
    status_code=status.HTTP_200_OK,
)
async def start_game(
    payload: schemas.GameStartRequest,
    _auth=Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    game = await session.get(models.Game, payload.game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game not found"
        )
    if game.status == models.GameStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game already started"
        )
    if game.status == models.GameStatus.STOPPED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game is stopped"
        )

    tasks = await get_game_tasks(game, session)
    if len(tasks) < game.tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pool has {len(tasks)} tasks, but game requires {game.tasks}",
        )

    game.started_at = datetime.now(timezone.utc)
    game.status = models.GameStatus.ACTIVE
    await session.commit()
    return schemas.GameStartResponse(id=game.id, status=game.status)


@app.post(
    "/v1/add",
    response_model=schemas.TaskAddResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_task(
    payload: schemas.TaskAddRequest,
    _auth=Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    task = await session.scalar(
        select(models.Task).where(
            models.Task.pool == payload.pool, models.Task.name == payload.name
        )
    )
    if task:
        task.answer = payload.answer
        task.statement = payload.statement
        task.base_cost = pick(payload.base_cost, settings.base_task_cost)
    else:
        task = models.Task(
            pool=payload.pool,
            name=payload.name,
            statement=payload.statement,
            answer=payload.answer,
            base_cost=pick(payload.base_cost, settings.base_task_cost),
        )
        session.add(task)
    await session.commit()
    return schemas.TaskAddResponse(
        id=task.id,
        pool=task.pool,
        name=task.name,
        statement=task.statement,
        base_cost=task.base_cost,
    )


@app.post(
    "/v1/add_pool",
    response_model=schemas.TaskBulkAddResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_task_pool(
    payload: schemas.TaskBulkAddRequest,
    _auth=Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    names = [item.name for item in payload.tasks]
    if len(names) != len(set(names)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task names inside one pool upload must be unique",
        )

    existing_result = await session.execute(
        select(models.Task).where(
            models.Task.pool == payload.pool, models.Task.name.in_(names)
        )
    )
    existing = {task.name: task for task in existing_result.scalars().all()}

    created = 0
    updated = 0
    tasks: list[models.Task] = []
    for item in payload.tasks:
        task = existing.get(item.name)
        if task:
            task.answer = item.answer
            task.statement = item.statement
            task.base_cost = pick(item.base_cost, settings.base_task_cost)
            updated += 1
        else:
            task = models.Task(
                pool=payload.pool,
                name=item.name,
                statement=item.statement,
                answer=item.answer,
                base_cost=pick(item.base_cost, settings.base_task_cost),
            )
            session.add(task)
            created += 1
        tasks.append(task)

    await session.commit()
    return schemas.TaskBulkAddResponse(
        pool=payload.pool,
        created=created,
        updated=updated,
        tasks=[
            schemas.TaskAddResponse(
                id=task.id,
                pool=task.pool,
                name=task.name,
                statement=task.statement,
                base_cost=task.base_cost,
            )
            for task in tasks
        ],
    )


@app.post(
    "/v1/stop",
    response_model=schemas.GameStopResponse,
    status_code=status.HTTP_200_OK,
)
async def stop_game(
    payload: schemas.GameStopRequest,
    _auth=Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    game = await session.get(models.Game, payload.game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game not found"
        )
    if game.status == models.GameStatus.STOPPED:
        return schemas.GameStopResponse(id=game.id, status=game.status)

    game.status = models.GameStatus.STOPPED
    game.stopped_at = datetime.now(timezone.utc)
    await session.commit()
    return schemas.GameStopResponse(id=game.id, status=game.status)


@app.post(
    "/v1/register",
    response_model=schemas.RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_player(
    payload: schemas.RegisterRequest, session: AsyncSession = Depends(get_session)
):
    game = await session.get(models.Game, payload.game_id)
    if game:
        game = await maybe_stop_expired(game, session)
    if not game or game.status == models.GameStatus.STOPPED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game not available"
        )

    player_count = await registered_player_count(payload.game_id, session)
    if player_count >= game.players:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Player limit reached for this game",
        )

    token = secrets.token_hex(16)
    player = models.Player(
        game_id=payload.game_id,
        team_name=payload.team_name or f"Team {player_count + 1}",
        members=encode_members(payload.members),
        token=token,
    )
    session.add(player)
    await session.commit()
    return schemas.RegisterResponse(
        token=token,
        player_id=player.id,
        team_name=player.team_name,
        members=decode_members(player.members),
    )


@app.get("/v1/status", response_model=schemas.StatusResponse)
async def get_status(context=Depends(require_player)):
    player, game, session = context
    game = await maybe_stop_expired(game, session)
    if game.status != models.GameStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game not active"
        )

    tasks = await get_game_tasks(game, session)
    counters = await get_task_counters(game.id, session)

    solved_rows = await session.execute(
        select(
            models.PlayerSolved.task_id,
            models.PlayerSolved.exchange,
            models.PlayerSolved.cost,
        ).where(
            models.PlayerSolved.player_id == player.id,
            models.PlayerSolved.game_id == game.id,
        )
    )
    solved_by_player = {
        (task_id, exchange): cost for task_id, exchange, cost in solved_rows.all()
    }

    my_attempt_rows = await session.execute(
        select(
            models.Submission.task_id,
            models.Submission.exchange,
            func.count(models.Submission.id),
        )
        .where(
            models.Submission.player_id == player.id,
            models.Submission.game_id == game.id,
            models.Submission.banned.is_(False),
        )
        .group_by(models.Submission.task_id, models.Submission.exchange)
    )
    my_attempt_counts = {
        (task_id, exchange): count for task_id, exchange, count in my_attempt_rows.all()
    }

    now = datetime.now(timezone.utc)
    statuses = []
    for task in tasks:
        for exchange in range(1, game.exchanges + 1):
            key = (task.id, exchange)
            solved_by_me = key in solved_by_player
            wrong_attempts = counters.wrong_count(key)
            wrong_attempts_left = max(0, game.wrong_attempt_limit - wrong_attempts)
            statuses.append(
                schemas.TaskStatus(
                    task_id=task.id,
                    name=task.name,
                    statement=task.statement,
                    exchange=exchange,
                    base_cost=task.base_cost,
                    cost=counters.cost(task, game, exchange, now=now),
                    solved_by_me=solved_by_me,
                    my_solved_cost=solved_by_player.get(key),
                    can_submit=not solved_by_me,
                    attempts=counters.attempt_count(key),
                    my_attempts=my_attempt_counts.get(key, 0),
                    wrong_attempts=wrong_attempts,
                    wrong_attempts_left=wrong_attempts_left,
                    wrong_limit_reached=wrong_attempts_left == 0,
                    solves=counters.solve_count(key),
                )
            )
    return schemas.StatusResponse(
        game_id=game.id,
        game=await game_info(game, session),
        player=player_info(player),
        tasks=statuses,
    )


@app.post("/v1/submit", response_model=schemas.SubmitResponse)
async def submit_solution(
    payload: schemas.SubmitRequest, context=Depends(require_player)
):
    player, game, session = context
    game = await maybe_stop_expired(game, session)
    if game.status != models.GameStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game not active"
        )
    if payload.exchange > game.exchanges:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exchange not found for this game",
        )

    tasks = await get_game_tasks(game, session)
    task_by_id = {task.id: task for task in tasks}
    task = task_by_id.get(payload.task)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task not found for this game",
        )

    key = (task.id, payload.exchange)
    counters = await get_task_counters(game.id, session)
    current_cost = counters.cost(task, game, payload.exchange)

    already_solved = await session.scalar(
        select(models.PlayerSolved).where(
            models.PlayerSolved.player_id == player.id,
            models.PlayerSolved.game_id == game.id,
            models.PlayerSolved.task_id == task.id,
            models.PlayerSolved.exchange == payload.exchange,
        )
    )
    if already_solved:
        return schemas.SubmitResponse(
            accepted=False,
            task_id=task.id,
            exchange=payload.exchange,
            cost=current_cost,
            solved_by_me=True,
            attempts=await player_attempt_count(player.id, game.id, key, session),
            wrong_attempts=counters.wrong_count(key),
            solves=counters.solve_count(key),
        )

    accepted = normalize_answer(payload.solution) == normalize_answer(task.answer)
    wrong_attempts_before = counters.wrong_count(key)
    if not accepted and wrong_attempts_before >= game.wrong_attempt_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Wrong submit limit reached for this task/exchange",
        )

    submission = models.Submission(
        player_id=player.id,
        game_id=game.id,
        task_id=task.id,
        exchange=payload.exchange,
        answer=payload.solution,
        accepted=accepted,
        cost=current_cost,
    )
    session.add(submission)

    if accepted:
        await session.flush()
        session.add(
            models.PlayerSolved(
                player_id=player.id,
                game_id=game.id,
                task_id=task.id,
                submission_id=submission.id,
                exchange=payload.exchange,
                cost=current_cost,
            )
        )

    await session.commit()
    wrong_attempts = wrong_attempts_before + (0 if accepted else 1)
    response_cost = (
        current_cost
        if accepted
        else compute_cost(
            task,
            game,
            payload.exchange,
            counters.solve_count(key),
            wrong_attempts,
        )
    )
    return schemas.SubmitResponse(
        accepted=accepted,
        task_id=task.id,
        exchange=payload.exchange,
        cost=response_cost,
        solved_by_me=accepted,
        attempts=await player_attempt_count(player.id, game.id, key, session),
        wrong_attempts=wrong_attempts,
        solves=counters.solve_count(key) + (1 if accepted else 0),
    )


async def player_attempt_count(
    player_id: int, game_id: str, key: tuple[int, int], session: AsyncSession
) -> int:
    task_id, exchange = key
    return (
        await session.scalar(
            select(func.count())
            .select_from(models.Submission)
            .where(
                models.Submission.player_id == player_id,
                models.Submission.game_id == game_id,
                models.Submission.task_id == task_id,
                models.Submission.exchange == exchange,
                models.Submission.banned.is_(False),
            )
        )
        or 0
    )


@app.get(
    "/v1/games/{game_id}/submissions",
    response_model=schemas.SubmissionListResponse,
)
async def list_game_submissions(
    game_id: str,
    _auth=Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    game = await session.get(models.Game, game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Game not found"
        )

    submissions_result = await session.execute(
        select(models.Submission)
        .where(models.Submission.game_id == game_id)
        .order_by(models.Submission.created_at, models.Submission.id)
    )
    submissions = list(submissions_result.scalars().all())

    players_result = await session.execute(
        select(models.Player).where(models.Player.game_id == game_id)
    )
    players = {player.id: player for player in players_result.scalars().all()}

    tasks = await get_game_tasks(game, session)
    tasks_by_id = {task.id: task for task in tasks}

    return schemas.SubmissionListResponse(
        game_id=game_id,
        submissions=[
            schemas.SubmissionAdmin(
                id=submission.id,
                game_id=submission.game_id,
                player_id=submission.player_id,
                team_name=players[submission.player_id].team_name,
                task_id=submission.task_id,
                task_name=tasks_by_id[submission.task_id].name,
                exchange=submission.exchange,
                submitted_answer=submission.answer,
                accepted=submission.accepted,
                cost=submission.cost,
                banned=submission.banned,
                created_at=submission.created_at,
            )
            for submission in submissions
        ],
    )


@app.post(
    "/v1/submissions/{submission_id}/ban",
    response_model=schemas.SubmissionBanResponse,
)
async def ban_submission(
    submission_id: int,
    _auth=Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    submission = await session.get(models.Submission, submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
        )

    removed_solve = False
    if not submission.banned and submission.accepted:
        result = await session.execute(
            delete(models.PlayerSolved).where(
                (models.PlayerSolved.submission_id == submission.id)
                | (
                    (models.PlayerSolved.submission_id.is_(None))
                    & (models.PlayerSolved.player_id == submission.player_id)
                    & (models.PlayerSolved.game_id == submission.game_id)
                    & (models.PlayerSolved.task_id == submission.task_id)
                    & (models.PlayerSolved.exchange == submission.exchange)
                )
            )
        )
        removed_solve = bool(result.rowcount)

    submission.banned = True
    await session.commit()
    return schemas.SubmissionBanResponse(
        id=submission.id,
        banned=submission.banned,
        accepted=submission.accepted,
        removed_solve=removed_solve,
    )


@app.get("/v1/leaderboard/{game_id}", response_model=schemas.LeaderboardResponse)
async def get_leaderboard(
    game_id: str,
    session: AsyncSession = Depends(get_session),
):
    game = await session.get(models.Game, game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Game not found"
        )
    game = await maybe_stop_expired(game, session)

    tasks = await get_game_tasks(game, session)
    counters = await get_task_counters(game.id, session)

    players_result = await session.execute(
        select(models.Player)
        .where(models.Player.game_id == game.id)
        .order_by(models.Player.id)
    )
    players = list(players_result.scalars().all())
    players_by_id = {player.id: player for player in players}

    solves_result = await session.execute(
        select(models.PlayerSolved).where(models.PlayerSolved.game_id == game.id)
    )
    solves = list(solves_result.scalars().all())
    solves_by_player: dict[int, list[models.PlayerSolved]] = defaultdict(list)
    solves_by_task: dict[TaskKey, list[models.PlayerSolved]] = defaultdict(list)
    for solve in solves:
        solves_by_player[solve.player_id].append(solve)
        solves_by_task[(solve.task_id, solve.exchange)].append(solve)

    attempt_rows = await session.execute(
        select(
            models.Submission.player_id,
            func.count(models.Submission.id),
            func.sum(models.Submission.accepted.cast(Integer)),
        )
        .where(
            models.Submission.game_id == game.id,
            models.Submission.banned.is_(False),
        )
        .group_by(models.Submission.player_id)
    )
    attempts_by_player = {
        player_id: (attempts, accepted or 0)
        for player_id, attempts, accepted in attempt_rows.all()
    }

    player_rows = []
    for player in players:
        player_solves = solves_by_player.get(player.id, [])
        attempts, accepted = attempts_by_player.get(player.id, (0, 0))
        score = sum(solve.cost for solve in player_solves)
        last_solve_at = as_utc(
            max((solve.solved_at for solve in player_solves), default=None)
        )
        player_rows.append(
            {
                "player_id": player.id,
                "team_name": player.team_name,
                "members": decode_members(player.members),
                "score": score,
                "solves": len(player_solves),
                "attempts": attempts,
                "wrong_attempts": max(0, attempts - accepted),
                "last_solve_at": last_solve_at,
            }
        )

    player_rows.sort(
        key=lambda row: (
            -row["score"],
            row["last_solve_at"] or datetime.max.replace(tzinfo=timezone.utc),
            row["player_id"],
        )
    )
    leaderboard_players = [
        schemas.LeaderboardPlayer(rank=index + 1, **row)
        for index, row in enumerate(player_rows)
    ]

    now = datetime.now(timezone.utc)
    leaderboard_tasks = []
    for task in tasks:
        for exchange in range(1, game.exchanges + 1):
            key = (task.id, exchange)
            task_solves = sorted(
                solves_by_task.get(key, []), key=lambda solve: solve.solved_at
            )
            leaderboard_tasks.append(
                schemas.LeaderboardTask(
                    task_id=task.id,
                    name=task.name,
                    statement=task.statement,
                    exchange=exchange,
                    base_cost=task.base_cost,
                    current_cost=counters.cost(task, game, exchange, now=now),
                    solves=counters.solve_count(key),
                    attempts=counters.attempt_count(key),
                    wrong_attempts=counters.wrong_count(key),
                    solved_by=[
                        schemas.LeaderboardSolve(
                            player_id=solve.player_id,
                            team_name=players_by_id[solve.player_id].team_name,
                            cost=solve.cost,
                            solved_at=solve.solved_at,
                        )
                        for solve in task_solves
                    ],
                )
            )

    return schemas.LeaderboardResponse(
        game_id=game.id,
        status=game.status,
        players=leaderboard_players,
        tasks=leaderboard_tasks,
    )
