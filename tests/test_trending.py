from pathlib import Path

from repo_courier.trending import parse_trending_html


def test_parse_trending_html() -> None:
    html = (Path(__file__).parent / "fixtures" / "trending.html").read_text(encoding="utf-8")
    repositories = parse_trending_html(html, limit=10)

    assert len(repositories) == 2
    assert repositories[0].full_name == "acme/rocket"
    assert repositories[0].stars == 12_345
    assert repositories[0].forks == 678
    assert repositories[0].stars_today == 1_234
    assert repositories[1].stars == 9_800


def test_limit_is_applied() -> None:
    html = (Path(__file__).parent / "fixtures" / "trending.html").read_text(encoding="utf-8")
    assert len(parse_trending_html(html, limit=1)) == 1
