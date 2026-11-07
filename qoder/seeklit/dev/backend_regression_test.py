"""Run a small regression suite against the existing embedded seekdb data."""

from pathlib import Path
import sys


BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from main import SearchFilters, SearchRequest, health, search  # noqa: E402


def main() -> None:
    status = health()
    assert status["papers"] == 48, status

    unfiltered = search(SearchRequest(
        query="大模型如何利用外部知识",
        mode="hybrid",
        n_results=10,
    ))
    assert unfiltered["hits"], unfiltered
    assert unfiltered["hits"][0]["paper"]["id"] == "ai005", unfiltered["hits"][0]

    by_year = search(SearchRequest(
        query="数据库",
        mode="hybrid",
        n_results=20,
        filters=SearchFilters(year_min=2020),
    ))
    years = [hit["paper"]["year"] for hit in by_year["hits"]]
    assert years and all(year >= 2020 for year in years), years

    by_tag = search(SearchRequest(
        query="检索增强生成",
        mode="hybrid",
        n_results=10,
        filters=SearchFilters(tags=["RAG"]),
    ))
    tag_ids = [hit["paper"]["id"] for hit in by_tag["hits"]]
    assert "ai005" in tag_ids, tag_ids
    assert all("RAG" in hit["paper"]["tags"] for hit in by_tag["hits"]), by_tag["hits"]

    print(f"backend regression passed: {status['papers']} papers")
    print(f"year_filter={years}")
    print(f"tag_filter={tag_ids}")


if __name__ == "__main__":
    main()
