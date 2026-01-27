from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def generate_uuid() -> str:
    return str(uuid4())


class GameStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    STOPPED = "stopped"


class Game(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    status: Mapped[GameStatus] = mapped_column(
        SAEnum(GameStatus, name="game_status"), default=GameStatus.CREATED, index=True
    )
    exchanges: Mapped[int] = mapped_column(Integer)
    tasks: Mapped[int] = mapped_column(Integer)
    players: Mapped[int] = mapped_column(Integer)
    pool: Mapped[str] = mapped_column(String(100))
    base_cost: Mapped[int] = mapped_column(Integer, default=100)
    cost_growth_per_minute: Mapped[int] = mapped_column(Integer, default=5)
    submit_penalty: Mapped[int] = mapped_column(Integer, default=10)
    solve_bonus: Mapped[int] = mapped_column(Integer, default=20)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pool: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(100))
    answer: Mapped[str] = mapped_column(String(255))


class TaskState(Base):
    __tablename__ = "task_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    exchange: Mapped[int] = mapped_column(Integer)
    base_cost: Mapped[int] = mapped_column(Integer)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    solve_count: Mapped[int] = mapped_column(Integer, default=0)
    solved: Mapped[bool] = mapped_column(Boolean, default=False)
    solved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    solved_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "game_id", "task_id", "exchange", name="uq_game_task_exchange"
        ),
    )


class PlayerSolved(Base):
    __tablename__ = "player_solved"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    game_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    exchange: Mapped[int] = mapped_column(Integer)
    cost_at_solve: Mapped[int] = mapped_column(Integer)
    solved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "player_id", "game_id", "task_id", "exchange", name="uq_player_game_task_exchange"
        ),
    )
