from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
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
    exchange_step_percent: Mapped[int] = mapped_column(Integer, default=10)
    solve_discount_percent: Mapped[int] = mapped_column(Integer, default=10)
    wrong_attempt_limit: Mapped[int] = mapped_column(Integer, default=5)
    wrong_attempt_growth_percent: Mapped[int] = mapped_column(Integer, default=3)
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
    team_name: Mapped[str] = mapped_column(String(100))
    members: Mapped[str] = mapped_column(Text, default="[]")
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pool: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(100))
    statement: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(String(255))
    base_cost: Mapped[int] = mapped_column(Integer, default=100)

    __table_args__ = (UniqueConstraint("pool", "name", name="uq_task_pool_name"),)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    game_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    exchange: Mapped[int] = mapped_column(Integer)
    answer: Mapped[str] = mapped_column(String(255))
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    cost: Mapped[int] = mapped_column(Integer)
    banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
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
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    submission_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True
    )
    exchange: Mapped[int] = mapped_column(Integer)
    cost: Mapped[int] = mapped_column(Integer)
    solved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "game_id",
            "task_id",
            "exchange",
            name="uq_player_game_task_exchange",
        ),
    )
