from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import secrets
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas
from app.config import get_settings
from app.db import Base, engine, get_session
from app.utils import pick

admin_scheme = HTTPBearer(auto_error=True)
player_scheme = HTTPBearer(auto_error=True)
settings = get_settings()


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


def compute_cost(
    state: models.TaskState, game: models.Game, *, now: datetime | None = None
) -> int:
    now = now or datetime.now(timezone.utc)
    start_time = game.started_at or game.created_at or now
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)

    solved_at = state.solved_at
    if solved_at and solved_at.tzinfo is None:
        solved_at = solved_at.replace(tzinfo=timezone.utc)

    end_time = solved_at if solved_at and solved_at < now else now
    elapsed_minutes = max(0, int((end_time - start_time).total_seconds() // 60))
    cost = state.base_cost + game.cost_growth_per_minute * elapsed_minutes

    if state.attempt_count:
        cost *= 1 + (game.submit_penalty / 100) * state.attempt_count

    if solved_at:
        cost *= max(0, 1 - game.solve_bonus / 100)

    return int(max(cost, 0))


async def maybe_stop_expired(game: models.Game, session: AsyncSession) -> models.Game:
    """Stop the game if duration elapsed."""
    if (
        game.status == models.GameStatus.ACTIVE
        and game.started_at
        and game.duration_minutes
    ):
        now = datetime.now(timezone.utc)
        if game.started_at.tzinfo is None:
            start_time = game.started_at.replace(tzinfo=timezone.utc)
        else:
            start_time = game.started_at
        if now >= start_time + timedelta(minutes=game.duration_minutes):
            game.status = models.GameStatus.STOPPED
            game.stopped_at = now
            await session.commit()
    return game


@app.get("/health")
async def health_check():
    return {"status": "ok"}


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
    base_cost = pick(payload.base_cost, settings.base_task_cost)
    growth = pick(payload.cost_growth_per_minute, settings.cost_growth_per_minute)
    submit_penalty = pick(payload.submit_penalty, settings.submit_penalty)
    solve_bonus = pick(payload.solve_bonus, settings.solve_bonus)

    game = models.Game(
        id=game_code(),
        status=models.GameStatus.CREATED,
        exchanges=payload.exchanges,
        tasks=payload.tasks,
        players=payload.players,
        pool=payload.pool,
        base_cost=base_cost,
        cost_growth_per_minute=growth,
        submit_penalty=submit_penalty,
        solve_bonus=solve_bonus,
        duration_minutes=payload.duration_minutes,
    )
    session.add(game)
    await session.flush()

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

    result = await session.execute(
        select(models.Task)
        .where(models.Task.pool == game.pool)
        .order_by(models.Task.id)
        .limit(game.tasks)
    )
    tasks = list(result.scalars().all())

    if len(tasks) < game.tasks:
        start_idx = len(tasks) + 1
        new_tasks = [
            models.Task(
                pool=game.pool,
                name=f"{game.pool}-task-{i}",
                answer=f"answer-{i}",
            )
            for i in range(start_idx, game.tasks + 1)
        ]
        session.add_all(new_tasks)
        await session.flush()
        tasks.extend(new_tasks)

    states = []
    for task in tasks[: game.tasks]:
        for exchange in range(1, game.exchanges + 1):
            exchange_cost = game.base_cost
            states.append(
                models.TaskState(
                    game_id=game.id,
                    task_id=task.id,
                    exchange=exchange,
                    base_cost=exchange_cost,
                )
            )
    session.add_all(states)
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
    task = models.Task(pool=payload.pool, name=payload.name, answer=payload.answer)
    session.add(task)
    await session.flush()
    await session.commit()
    return schemas.TaskAddResponse(id=task.id, pool=task.pool, name=task.name)


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

    player_count = await session.scalar(
        select(func.count())
        .select_from(models.Player)
        .where(models.Player.game_id == payload.game_id)
    )
    if player_count >= game.players:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Player limit reached for this game",
        )

    token = secrets.token_hex(16)
    session.add(models.Player(game_id=payload.game_id, token=token))
    await session.commit()
    return schemas.RegisterResponse(token=token)


@app.get("/v1/status", response_model=schemas.StatusResponse)
async def get_status(context=Depends(require_player)):
    player, game, session = context
    game = await maybe_stop_expired(game, session)
    if game.status != models.GameStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Game not active"
        )

    solved_rows = await session.execute(
        select(
            models.PlayerSolved.task_id,
            models.PlayerSolved.exchange,
            models.PlayerSolved.cost_at_solve,
        ).where(
            models.PlayerSolved.player_id == player.id,
            models.PlayerSolved.game_id == game.id,
        )
    )
    solved_by_player: dict[tuple[int, int], int] = {
        (task_id, exchange): cost for task_id, exchange, cost in solved_rows.all()
    }

    result = await session.execute(
        select(models.TaskState).where(models.TaskState.game_id == game.id)
    )
    states = result.scalars().all()
    tasks = []
    now = datetime.now(timezone.utc)
    for state in states:
        tasks.append(
            schemas.TaskStatus(
                task_id=state.task_id,
                exchange=state.exchange,
                cost=(
                    state.solved_cost
                    if state.solved_cost is not None
                    else compute_cost(state, game, now=now)
                ),
                solved=state.solved,
                solved_by_me=(state.task_id, state.exchange) in solved_by_player,
                attempts=state.attempt_count,
                solves=state.solve_count,
            )
        )
    return schemas.StatusResponse(game_id=game.id, tasks=tasks)


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
    result = await session.execute(
        select(models.TaskState).where(
            models.TaskState.game_id == game.id,
            models.TaskState.task_id == payload.task,
            models.TaskState.exchange == payload.exchange,
        )
    )
    task_state = result.scalar_one_or_none()
    if not task_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task not found for this game/exchange",
        )

    task = await session.get(models.Task, payload.task)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task not found for this game",
        )

    task_state.attempt_count += 1
    normalized_solution = payload.solution.strip().lower()
    normalized_answer = task.answer.strip().lower()

    if task_state.solved or normalized_solution != normalized_answer:
        await session.commit()
        return schemas.SubmitResponse(
            accepted=False,
            task_id=task_state.task_id,
            exchange=task_state.exchange,
            cost=compute_cost(task_state, game),
            solved=task_state.solved,
            attempts=task_state.attempt_count,
        )

    task_state.solved = True
    task_state.solve_count += 1
    task_state.solved_at = datetime.now(timezone.utc)
    solved_cost = compute_cost(task_state, game)
    if task_state.solved_cost is None:
        task_state.solved_cost = solved_cost
    session.add(
        models.PlayerSolved(
            player_id=player.id,
            game_id=game.id,
            task_id=payload.task,
            exchange=payload.exchange,
            cost_at_solve=solved_cost,
        )
    )
    await session.commit()

    return schemas.SubmitResponse(
        accepted=True,
        task_id=task_state.task_id,
        exchange=task_state.exchange,
        cost=solved_cost,
        solved=task_state.solved,
        attempts=task_state.attempt_count,
    )
