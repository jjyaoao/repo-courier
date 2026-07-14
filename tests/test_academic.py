import json
import logging
from datetime import date, datetime, timezone

from repo_courier.academic.analyzer import PaperAnalyzer
from repo_courier.academic.arxiv import ArxivSource, build_query, extract_introduction, parse_feed
from repo_courier.academic.base import SearchWindow
from repo_courier.academic.pipeline import AcademicPipeline, analysis_worker_count, rule_score
from repo_courier.academic.prompts import (
    PAPER_ANALYSIS_SYSTEM_PROMPT,
    paper_analysis_user_prompt,
)
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


def test_arxiv_fetches_pages_with_interval_before_rule_ranking() -> None:
    calls: list[dict[str, object]] = []
    sleeps: list[float] = []

    class Response:
        status_code = 200

        def __init__(self, content: str) -> None:
            self.text = content

        def raise_for_status(self) -> None:
            return None

    class Client:
        def get(self, url, params):
            calls.append(params)
            start = int(params["start"])
            size = min(int(params["max_results"]), 250 - start)
            entries = "".join(
                f"""<entry><id>http://arxiv.org/abs/2607.{index:05d}v1</id>
                <published>2026-07-12T01:00:00Z</published><title>agent {index}</title>
                <summary>agent abstract</summary></entry>"""
                for index in range(start, start + size)
            )
            return Response(f'<feed xmlns="http://www.w3.org/2005/Atom">{entries}</feed>')

    source = ArxivSource(
        ArxivConfig(candidate_limit=250, page_size=100, request_interval_seconds=3),
        client=Client(),
        sleeper=sleeps.append,
    )
    papers = source.fetch(
        ProfileConfig(interests=["agent"], exclude_keywords=[]),
        SearchWindow.for_beijing_day(date(2026, 7, 12)),
    )

    assert [call["start"] for call in calls] == [0, 100, 200]
    assert [call["max_results"] for call in calls] == [100, 100, 50]
    assert sleeps == [3, 3]
    assert len(papers) == 250
    assert papers[0].source_id == "2607.00000"


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
            paper.research_motivation = "研究动机"
            paper.core_contributions = "核心贡献"
            paper.analysis_status = "ai"

    analyzer = Analyzer()
    pipeline = AcademicPipeline(
        AcademicConfig(
            enabled=True,
            arxiv=ArxivConfig(final_picks=2, max_analysis_workers=1),
        ),
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
    assert result.papers[0].combined_score == 9.4


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
    assert "LLM 分析失败" in paper.research_motivation
    assert "A useful abstract" in paper.core_contributions
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
                                "'research_motivation': '现有方法可靠性不足', "
                                "'core_contributions': '提出新的智能体协作方法',}\n```"
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
        AcademicConfig(
            enabled=True,
            api_key="secret",
            base_url="https://www.dmxapi.cn/v1",
            model="model",
        ),
        SummaryConfig(model="model"),
        client=Client(),
    )

    analyzer.analyze(paper, ProfileConfig(interests=["agent"]))

    assert '"relevance_score": 9' in PAPER_ANALYSIS_SYSTEM_PROMPT
    assert "keywords 与 paper_content" in PAPER_ANALYSIS_SYSTEM_PROMPT
    assert "分别不超过 200 字" in PAPER_ANALYSIS_SYSTEM_PROMPT
    assert paper.relevance_score == 9
    assert paper.innovation_score == 8
    assert paper.research_motivation == "现有方法可靠性不足"
    assert paper.core_contributions == "提出新的智能体协作方法"
    assert paper.analysis_status == "ai"


def test_llm_raw_response_is_logged(caplog) -> None:
    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"relevance_score": 9, "innovation_score": 8, '
                                '"research_motivation": "需要提升可靠性", '
                                '"core_contributions": "提出新的协作方法"}'
                            )
                        }
                    }
                ]
            }

    class Client:
        def post(self, *args, **kwargs):
            return Response()

    paper = _paper("logged-paper", "Agent", "Abstract")
    analyzer = PaperAnalyzer(
        AcademicConfig(enabled=True, api_key="secret", model="model"),
        SummaryConfig(model="model"),
        client=Client(),
    )

    with caplog.at_level(logging.INFO, logger="repo_courier.academic.analyzer"):
        analyzer.analyze(paper, ProfileConfig(interests=["agent"]))

    assert "logged-paper HTTP 200 响应体" in caplog.text
    assert '"innovation_score": 8' in caplog.text


def test_llm_response_without_choices_logs_body_and_explains_shape(caplog) -> None:
    class Response:
        status_code = 200
        text = '{"code":"InvalidParameter","message":"model is unavailable"}'

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "code": "InvalidParameter",
                "message": "model is unavailable",
            }

    class Client:
        def post(self, *args, **kwargs):
            return Response()

    paper = _paper("invalid-response", "Agent", "Abstract")
    analyzer = PaperAnalyzer(
        AcademicConfig(enabled=True, api_key="secret", model="model"),
        SummaryConfig(model="model"),
        client=Client(),
    )

    with caplog.at_level(logging.INFO, logger="repo_courier.academic.analyzer"):
        analyzer.analyze(paper, ProfileConfig(interests=["agent"]))

    assert 'invalid-response HTTP 200 响应体：{"code":"InvalidParameter"' in caplog.text
    assert "缺少非空 choices，顶层字段：code, message" in caplog.text
    assert paper.analysis_status == "fallback"


def test_academic_model_is_sent_independently_from_summary_model() -> None:
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"relevance_score": 9, "innovation_score": 8, '
                                '"research_motivation": "需要提升可靠性", '
                                '"core_contributions": "提出新的协作方法"}'
                            )
                        }
                    }
                ]
            }

    class Client:
        request_url = None
        request_json = None

        def post(self, *args, **kwargs):
            self.request_url = args[0]
            self.request_json = kwargs["json"]
            return Response()

    client = Client()
    analyzer = PaperAnalyzer(
        AcademicConfig(
            enabled=True,
            api_key="secret",
            base_url="https://idealab.alibaba-inc.com/api/v1/chat/completions",
            model="bigmodel/GLM-5",
        ),
        SummaryConfig(model="github-summary-model"),
        client=client,
    )

    analyzer.analyze(_paper("model-paper", "Agent", "Abstract"), ProfileConfig())

    assert client.request_url == "https://idealab.alibaba-inc.com/api/v1/chat/completions"
    assert client.request_json["model"] == "bigmodel/GLM-5"


def test_fallback_fields_are_each_limited_to_200_characters() -> None:
    paper = _paper("1", "Agent", "摘" * 300)

    PaperAnalyzer(AcademicConfig(), SummaryConfig(enabled=False)).analyze(
        paper, ProfileConfig()
    )

    assert len(paper.research_motivation) <= 200
    assert len(paper.core_contributions) == 200
    assert paper.core_contributions.endswith("…")


def test_non_object_llm_json_falls_back_instead_of_crashing() -> None:
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "[]"}}]}

    class Client:
        def post(self, *args, **kwargs):
            return Response()

    paper = _paper("1", "Agent", "Abstract")
    analyzer = PaperAnalyzer(
        AcademicConfig(enabled=True, api_key="secret", model="model"),
        SummaryConfig(model="model"),
        client=Client(),
    )

    analyzer.analyze(paper, ProfileConfig(interests=["agent"]))

    assert paper.analysis_status == "fallback"


def test_llm_input_uses_title_abstract_and_optional_introduction() -> None:
    paper = _paper("1", "Paper title", "Paper abstract")
    without_intro = json.loads(
        paper_analysis_user_prompt(paper, ProfileConfig(interests=["agent"]))
    )["paper_content"]
    assert without_intro == "Title:\nPaper title\n\nAbstract:\nPaper abstract"
    assert "Introduction:" not in without_intro

    paper.introduction = "Paper introduction"
    with_intro = json.loads(
        paper_analysis_user_prompt(paper, ProfileConfig(interests=["agent"]))
    )["paper_content"]
    assert with_intro.endswith("Introduction:\nPaper introduction")
