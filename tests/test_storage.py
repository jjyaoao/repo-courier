import json
from datetime import date

from repo_courier.models import Repository
from repo_courier.storage import HistoryStore


def _repo(rank: int = 1) -> Repository:
    return Repository(rank=rank, owner="acme", name="rocket", url="https://example.com")


def test_history_applies_previous_rank(tmp_path) -> None:
    store = HistoryStore(tmp_path)
    store.save([_repo(rank=4)], date(2026, 7, 9))
    current = _repo(rank=1)

    store.apply_rank_history([current], date(2026, 7, 10))

    assert current.previous_rank == 4
    assert current.is_new is False
    assert current.rank_change == "↑3"


def test_history_save_is_valid_json(tmp_path) -> None:
    path = HistoryStore(tmp_path).save([_repo()], date(2026, 7, 10))
    assert json.loads(path.read_text(encoding="utf-8"))["date"] == "2026-07-10"
