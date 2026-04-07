import httpx
import pytest

from app.main import app


ADMIN_HEADERS = {"Authorization": "Bearer changeme"}


@pytest.mark.asyncio
async def test_wrong_submissions_increase_cost_until_cap():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        pool_response = await client.post(
            "/v1/add_pool",
            headers=ADMIN_HEADERS,
            json={
                "pool": "demo",
                "tasks": [
                    {"name": "A", "answer": "42", "base_cost": 100},
                ],
            },
        )
        assert pool_response.status_code == 201

        create_response = await client.post(
            "/v1/create",
            headers=ADMIN_HEADERS,
            json={
                "exchanges": 1,
                "tasks": 1,
                "players": 2,
                "pool": "demo",
                "cost_growth_per_minute": 0,
                "exchange_step_percent": 10,
                "solve_discount_percent": 10,
                "wrong_attempt_limit": 5,
                "wrong_attempt_growth_percent": 3,
            },
        )
        assert create_response.status_code == 201
        game_id = create_response.json()["id"]

        start_response = await client.post(
            "/v1/start", headers=ADMIN_HEADERS, json={"game_id": game_id}
        )
        assert start_response.status_code == 200

        player_response = await client.post("/v1/register", json={"game_id": game_id})
        spectator_response = await client.post(
            "/v1/register", json={"game_id": game_id}
        )
        assert player_response.status_code == 201
        assert spectator_response.status_code == 201
        player_headers = {"Authorization": f"Bearer {player_response.json()['token']}"}
        spectator_headers = {
            "Authorization": f"Bearer {spectator_response.json()['token']}"
        }

        status_response = await client.get("/v1/status", headers=player_headers)
        assert status_response.status_code == 200
        task_id = status_response.json()["tasks"][0]["task_id"]
        assert status_response.json()["tasks"][0]["cost"] == 100

        wrong_costs = []
        for _ in range(5):
            submit_response = await client.post(
                "/v1/submit",
                headers=player_headers,
                json={"task": task_id, "exchange": 1, "solution": "wrong"},
            )
            assert submit_response.status_code == 200
            assert submit_response.json()["accepted"] is False
            wrong_costs.append(submit_response.json()["cost"])

        assert wrong_costs == [103, 106, 109, 112, 115]

        rejected_response = await client.post(
            "/v1/submit",
            headers=player_headers,
            json={"task": task_id, "exchange": 1, "solution": "wrong"},
        )
        assert rejected_response.status_code == 429
        assert rejected_response.json()["detail"] == (
            "Wrong submit limit reached for this task/exchange"
        )

        status_after_wrong = await client.get("/v1/status", headers=spectator_headers)
        task_status = status_after_wrong.json()["tasks"][0]
        assert task_status["cost"] == 115
        assert task_status["attempts"] == 5
        assert task_status["wrong_attempts"] == 5

        solve_response = await client.post(
            "/v1/submit",
            headers=player_headers,
            json={"task": task_id, "exchange": 1, "solution": "42"},
        )
        assert solve_response.status_code == 200
        assert solve_response.json()["accepted"] is True
        assert solve_response.json()["cost"] == 115

        leaderboard_response = await client.get(f"/v1/leaderboard/{game_id}")
        assert leaderboard_response.status_code == 200
        leaderboard = leaderboard_response.json()
        assert leaderboard["players"][0]["score"] == 115
        assert leaderboard["players"][0]["attempts"] == 6
        assert leaderboard["players"][0]["wrong_attempts"] == 5
        assert leaderboard["tasks"][0]["current_cost"] == 103
        assert leaderboard["tasks"][0]["wrong_attempts"] == 5
        assert leaderboard["tasks"][0]["solves"] == 1
