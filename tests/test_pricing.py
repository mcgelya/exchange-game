from datetime import datetime, timezone

from app.main import compute_cost
from app.models import Game, GameStatus, Task


def test_compute_cost_uses_wrong_attempt_growth():
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    game = Game(
        id="G-TEST",
        status=GameStatus.ACTIVE,
        exchanges=1,
        tasks=1,
        players=1,
        pool="demo",
        base_cost=100,
        cost_growth_per_minute=0,
        exchange_step_percent=10,
        solve_discount_percent=10,
        attempt_limit=6,
        wrong_attempt_growth_percent=3,
        created_at=started_at,
        started_at=started_at,
    )
    task = Task(id=1, pool="demo", name="A", answer="42", base_cost=100)

    assert compute_cost(task, game, exchange=1, solve_count=0) == 100
    assert (
        compute_cost(task, game, exchange=1, solve_count=0, wrong_attempt_count=1)
        == 103
    )
    assert (
        compute_cost(task, game, exchange=1, solve_count=0, wrong_attempt_count=5)
        == 115
    )
    assert (
        compute_cost(task, game, exchange=1, solve_count=0, wrong_attempt_count=6)
        == 118
    )
    assert (
        compute_cost(task, game, exchange=1, solve_count=1, wrong_attempt_count=6)
        == 106
    )


def test_compute_cost_uses_game_exchange_step():
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    game = Game(
        id="G-TEST",
        status=GameStatus.ACTIVE,
        exchanges=2,
        tasks=1,
        players=1,
        pool="demo",
        base_cost=100,
        cost_growth_per_minute=0,
        exchange_step_percent=25,
        solve_discount_percent=10,
        attempt_limit=6,
        wrong_attempt_growth_percent=3,
        created_at=started_at,
        started_at=started_at,
    )
    task = Task(id=1, pool="demo", name="A", answer="42", base_cost=100)

    assert compute_cost(task, game, exchange=1, solve_count=0) == 100
    assert compute_cost(task, game, exchange=2, solve_count=0) == 125
