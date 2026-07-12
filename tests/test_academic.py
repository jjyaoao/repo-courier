from datetime import date, datetime, timezone

from repo_courier.academic.analyzer import PaperAnalyzer
from repo_courier.academic.arxiv import build_query, extract_introduction, parse_feed
from repo_courier.academic.base import SearchWindow
from repo_courier.academic.pipeline import AcademicPipeline, analysis_worker_count, rule_score
from repo_courier.academic.prompts import PAPER_ANALYSIS_SYSTEM_PROMPT
from repo_courier.config import AcademicConfig, ArxivConfig, ProfileConfig, SummaryConfig
from repo_courier.models import AcademicPaper


def _paper(source_id: str, title: str, abstract: str, hour: int = 1) -> AcademicPaper:
    return AcademicPaper(
        source="arxiv",
        source_id=source_id,
        title=title,
        url=f"https://arxiv.org/abs/{source_id}",
        abstract=abstract,
        submitted_at=datetime(2026, 7, 12, hour, tzinfo=timezone.utc),
    )


def test_beijing_window_and_arxiv_query_use_utc_boundaries() -> None:
    window = SearchWindow.for_beijing_day(date(2026, 7, 12))
    profile = ProfileConfig(interests=["llm agent"], exclude_keywords=["survey"])

    query = build_query(profile, window)

    assert window.start_utc == datetime(2026, 7, 11, 16, tzinfo=timezone.utc)
    assert "all:\"llm agent\"" in query
    assert "ANDNOT all:\"survey\"" in query
    assert "submittedDate:[202607111600 TO 202607121559]" in query
    assert query.index("submittedDate") < query.index("ANDNOT")


def test_rule_score_weights_title_and_abstract() -> None:
    paper = _paper("1", "Agent systems", "agent workflows and tutorial collection")
    profile = ProfileConfig(interests=["agent"], exclude_keywords=["tutorial collection"])

    assert rule_score(paper, profile) == 3


def test_parse_feed_and_extract_introduction() -> None:
    feed = """<feed xmlns="http://www.w3.org/2005/Atom"><entry>
    <id>http://arxiv.org/abs/2607.00001v2</id><published>2026-07-12T01:00:00Z</published>
    <title> A paper </title><summary> Useful work. </summary>
    <author><name>Alice</name></author><link rel="alternate" href="https://arxiv.org/abs/2607.00001"/>
    </entry></feed>"""

    papers = parse_feed(feed)
    introduction = extract_introduction(
        "<html><h2>1 Introduction</h2><p>First paragraph.</p><p>Second.</p>"
        "<h2>2 Method</h2><p>Stop.</p></html>"
    )

    assert papers[0].source_id == "2607.00001"
    assert papers[0].authors == ["Alice"]
    assert introduction == "First paragraph.\n\nSecond."


def test_pipeline_shortlists_twice_final_picks_and_combines_scores() -> None:
    papers = [_paper(str(index), f"agent {index}", "agent") for index in range(6)]

    class Source:
        def fetch(self, profile, window):
            return papers

        def enrich_introduction(self, paper):
            paper.introduction = "intro"

    class Analyzer:
        analyzed: list[str] = []

        def analyze(self, paper, profile):
            self.analyzed.append(paper.source_id)
            paper.relevance_score = int(paper.source_id)
            paper.innovation_score = 10
            paper.summary = "summary"
            paper.analysis_status = "ai"

    analyzer = Analyzer()
    pipeline = AcademicPipeline(
        AcademicConfig(arxiv=ArxivConfig(final_picks=2, max_analysis_workers=1)),
        SummaryConfig(enabled=False),
        source=Source(),
        analyzer=analyzer,
    )

    result = pipeline.run(
        ProfileConfig(interests=["agent"], exclude_keywords=[]),
        SearchWindow.for_beijing_day(date(2026, 7, 12)),
    )

    assert len(analyzer.analyzed) == 4
    assert len(result.papers) == 2
    assert result.papers[0].combined_score == 5.1


def test_analysis_workers_are_dynamic_and_capped() -> None:
    assert analysis_worker_count(final_picks=3, max_workers=50, shortlist_count=6) == 6
    assert analysis_worker_count(final_picks=40, max_workers=50, shortlist_count=80) == 50
    assert analysis_worker_count(final_picks=3, max_workers=50, shortlist_count=4) == 4


def test_llm_fallback_uses_rule_score_and_abstract() -> None:
    paper = _paper("1", "Agent", "A useful abstract")
    paper.rule_score = 12

    PaperAnalyzer(AcademicConfig(), SummaryConfig(enabled=False)).analyze(
        paper, ProfileConfig()
    )

    assert paper.relevance_score == 10
    assert paper.innovation_score == 0
    assert paper.summary == "A useful abstract"
    assert paper.analysis_status == "fallback"


def test_prompt_has_explicit_json_example_and_repairs_llm_json() -> None:
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "```json\n{'relevance_score': 9, 'innovation_score': 8, "
                                "'summary': '相关论文',}\n```"
                            )
                        }
                    }
                ]
            }

    class Client:
        def post(self, *args, **kwargs):
            return Response()

    paper = _paper("1", "Agent", "Abstract")
    analyzer = PaperAnalyzer(
        AcademicConfig(api_key="secret", base_url="https://www.dmxapi.cn/v1"),
        SummaryConfig(model="model"),
        client=Client(),
    )

    analyzer.analyze(paper, ProfileConfig(interests=["agent"]))

    assert '"relevance_score": 9' in PAPER_ANALYSIS_SYSTEM_PROMPT
    assert "与用户关键词相关的方法与创新点" in PAPER_ANALYSIS_SYSTEM_PROMPT
    assert "不得超过 200 个字符" in PAPER_ANALYSIS_SYSTEM_PROMPT
    assert paper.relevance_score == 9
    assert paper.innovation_score == 8
    assert paper.summary == "相关论文"
    assert paper.analysis_status == "ai"


def test_analyzer_limits_ai_and_fallback_summaries_to_200_characters() -> None:
    paper = _paper("1", "Agent", "摘" * 300)

    PaperAnalyzer(AcademicConfig(), SummaryConfig(enabled=False)).analyze(
        paper, ProfileConfig()
    )

    assert len(paper.summary) == 200
    assert paper.summary.endswith("…")
