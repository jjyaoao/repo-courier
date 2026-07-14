from datetime import date

from repo_courier.academic.base import SearchWindow
from repo_courier.config import (
    AcademicConfig,
    FeedSourceConfig,
    ProfileConfig,
    SummaryConfig,
    TechBlogConfig,
    TechNewsConfig,
)
from repo_courier.feeds import (
    FeedAnalyzer,
    TechBlogPipeline,
    TechNewsPipeline,
    combined_score,
    parse_feed,
    score_post,
)
from repo_courier.models import TechBlogPost, TechNewsPost


def test_parse_rss_and_atom_entries() -> None:
    rss = """<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><item>
    <guid>blog-1</guid><title>Agent infrastructure</title>
    <link>https://example.com/blog-1</link>
    <description><![CDATA[<p>Agent summary</p>]]></description>
    <content:encoded><![CDATA[<p>Detailed MCP implementation.</p>]]></content:encoded>
    <category>Developer Tools</category><pubDate>Sun, 12 Jul 2026 01:00:00 GMT</pubDate>
    </item></channel></rss>"""
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry>
    <id>news-1</id><title>New AI platform</title>
    <link rel="alternate" href="https://example.com/news-1"/><summary>Cloud news</summary>
    <category term="AI"/><published>2026-07-12T02:00:00Z</published>
    </entry></feed>"""

    rss_entry = parse_feed(rss)[0]
    atom_entry = parse_feed(atom)[0]

    assert rss_entry.title == "Agent infrastructure"
    assert rss_entry.tags == ["Developer Tools"]
    assert "Detailed MCP implementation" in rss_entry.content
    assert atom_entry.url == "https://example.com/news-1"
    assert atom_entry.published_at is not None


def test_rule_score_uses_highest_field_weight_once_and_excludes() -> None:
    post = TechBlogPost(
        source_id="source:item",
        source_name="Source",
        title="Agent platform",
        url="https://example.com/item",
        tags=["automation"],
        content_excerpt="Agent and MCP implementation",
    )
    profile = ProfileConfig(
        interests=["agent", "automation", "mcp"], exclude_keywords=[]
    )

    assert score_post(post, profile) is True
    assert post.rule_score == 60
    assert post.matched_keywords == ["agent", "automation", "mcp"]

    post.content_excerpt += " tutorial collection"
    profile.exclude_keywords = ["tutorial collection"]
    assert score_post(post, profile) is False


def test_combined_scores_differ_for_blog_and_news() -> None:
    blog = TechBlogPost(
        source_id="blog",
        source_name="Source",
        title="Agent",
        url="https://example.com/blog",
        rule_score=60,
        relevance_score=8,
        technical_depth_score=7,
        analysis_status="ai",
    )
    news = TechNewsPost(
        source_id="news",
        source_name="Source",
        title="Agent launch",
        url="https://example.com/news",
        rule_score=60,
        relevance_score=8,
        importance_score=9,
        analysis_status="ai",
    )

    assert combined_score(blog) == 69.6
    assert combined_score(news) == 74.4


def test_llm_analyzer_uses_category_specific_secondary_score() -> None:
    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"choices": [{"message": {"content": self.payload}}]}

    class Client:
        def post(self, url, headers, json):
            category = json["messages"][1]["content"]
            secondary = (
                '"technical_depth_score": 7'
                if '"category": "tech_blog"' in category
                else '"importance_score": 9'
            )
            return Response(
                "{"
                '"relevance_score": 8,'
                f"{secondary},"
                '"summary": "中文摘要",'
                '"recommendation_reason": "值得关注"'
                "}"
            )

    analyzer = FeedAnalyzer(
        AcademicConfig(api_key="secret", model="model"),
        SummaryConfig(),
        client=Client(),
    )
    profile = ProfileConfig(interests=["agent"])
    blog = TechBlogPost("blog", "Source", "Agent", "https://example.com/blog")
    news = TechNewsPost("news", "Source", "Agent", "https://example.com/news")

    analyzer.analyze(blog, profile)
    analyzer.analyze(news, profile)

    assert blog.analysis_status == "ai"
    assert blog.technical_depth_score == 7
    assert news.analysis_status == "ai"
    assert news.importance_score == 9


def test_pipelines_keep_independent_final_limits() -> None:
    items = "".join(
        f"""<item><guid>{index}</guid><title>Agent release {index}</title>
        <link>https://example.com/{index}</link><description>MCP automation</description>
        <pubDate>Sun, 12 Jul 2026 0{index}:00:00 GMT</pubDate></item>"""
        for index in range(8)
    )
    feed = f"<rss><channel>{items}</channel></rss>"

    class Response:
        text = feed

        def raise_for_status(self) -> None:
            return None

    class Client:
        def get(self, url):
            return Response()

    class Analyzer:
        def analyze(self, post, profile):
            post.relevance_score = 8
            if isinstance(post, TechBlogPost):
                post.technical_depth_score = 7
            else:
                post.importance_score = 9
            post.summary = "中文摘要"
            post.recommendation_reason = "值得关注"
            post.analysis_status = "ai"

    source = [FeedSourceConfig("source", "Source", "https://example.com/feed")]
    common = {
        "academic": AcademicConfig(),
        "summary": SummaryConfig(enabled=False),
        "client": Client(),
        "analyzer": Analyzer(),
    }
    profile = ProfileConfig(interests=["agent"], exclude_keywords=[])
    window = SearchWindow.for_beijing_day(date(2026, 7, 12))

    blogs = TechBlogPipeline(
        TechBlogConfig(enabled=True, final_picks=5, sources=source), **common
    ).run(profile, window)
    news = TechNewsPipeline(
        TechNewsConfig(enabled=True, final_picks=3, sources=source), **common
    ).run(profile, window)

    assert len(blogs.posts) == 5
    assert len(news.posts) == 3
    assert [post.pick_rank for post in blogs.posts] == [1, 2, 3, 4, 5]
    assert [post.pick_rank for post in news.posts] == [1, 2, 3]
