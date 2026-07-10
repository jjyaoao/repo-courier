from repo_courier.config import SummaryConfig
from repo_courier.models import Repository
from repo_courier.summary import Summarizer


def test_fallback_summary_without_ai_credentials() -> None:
    repository = Repository(
        rank=1,
        owner="acme",
        name="agent-kit",
        url="https://github.com/acme/agent-kit",
        description="A toolkit for building LLM agents",
        language="Python",
        stars_today=321,
        topics=["llm", "agent"],
    )

    Summarizer(SummaryConfig(model="", api_key="")).summarize([repository])

    assert repository.summary == "A toolkit for building LLM agents"
    assert repository.category == "AI / 机器学习"
    assert any("321" in item for item in repository.highlights)
    assert repository.risk_note
