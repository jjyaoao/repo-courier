from repo_courier.config import ProfileConfig
from repo_courier.models import Repository
from repo_courier.personalize import Personalizer


def _repo(
    name: str,
    rank: int,
    *,
    topics: list[str] | None = None,
    description: str = "",
    stars_today: int = 0,
) -> Repository:
    return Repository(
        rank=rank,
        owner="acme",
        name=name,
        url=f"https://github.com/acme/{name}",
        topics=topics or [],
        description=description,
        stars_today=stars_today,
        license="MIT",
    )


def test_select_prefers_personal_relevance_over_trending_rank() -> None:
    popular_but_irrelevant = _repo("css-gallery", 1, stars_today=2_000)
    relevant = _repo(
        "agent-runner",
        12,
        topics=["agent", "mcp", "automation"],
        stars_today=300,
    )
    personalizer = Personalizer(
        ProfileConfig(interests=["agent", "mcp"], exclude_keywords=[], daily_picks=1)
    )

    picks = personalizer.select([popular_but_irrelevant, relevant])

    assert picks == [relevant]
    assert relevant.pick_rank == 1
    assert relevant.recommendation == "深挖"
    assert popular_but_irrelevant.recommendation == "略过"
    assert relevant.matched_interests == ["agent", "mcp"]
    assert "agent" in relevant.why_for_you


def test_exclude_keyword_reduces_score() -> None:
    normal = _repo("agent-runtime", 2, topics=["agent"])
    excluded = _repo(
        "awesome-agent-list",
        1,
        topics=["agent"],
        description="An awesome list of agent tutorials",
    )
    personalizer = Personalizer(
        ProfileConfig(
            interests=["agent"],
            exclude_keywords=["awesome list", "tutorial"],
            daily_picks=2,
        )
    )

    picks = personalizer.select([excluded, normal])

    assert picks[0] is normal
    assert excluded not in picks
    assert excluded.relevance_score < normal.relevance_score
    assert "过滤词" in excluded.why_for_you
