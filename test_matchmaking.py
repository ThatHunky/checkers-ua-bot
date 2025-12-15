import fakeredis
from repository import GameRepository


def setup_repo():
    repo = GameRepository("redis://localhost/0")
    repo.redis_client = fakeredis.FakeRedis(decode_responses=True)
    return repo


def test_enqueue_cancel_idempotent():
    repo = setup_repo()
    repo.mm_enqueue(1, 100, "rated", 1200)
    repo.mm_enqueue(1, 100, "rated", 1200)
    assert repo.mm_status(1)["status"] == "queued"
    assert repo.mm_cancel(1) is True
    assert repo.mm_status(1)["status"] == "cancelled"
    assert repo.mm_cancel(1) is False


def test_match_pairing_prefers_close_rating():
    repo = setup_repo()
    repo.mm_enqueue(1, 100, "rated", 1200)
    repo.mm_enqueue(2, 101, "rated", 1210)
    repo.mm_enqueue(3, 102, "rated", 1500)
    result = repo.mm_try_match("rated", base_delta=50, step=50, step_seconds=1, max_delta=400)
    assert result is not None
    users = {u["user_id"] for u in result["users"]}
    assert users == {1, 2}


def test_invite_flow():
    repo = setup_repo()
    repo.mm_create_invite(1, 100, "rated", "ABC123")
    invite = repo.mm_accept_invite(2, 200, "ABC123")
    assert invite is not None
    assert invite.get("status") == "used"
    again = repo.mm_accept_invite(3, 300, "ABC123")
    assert again is None
