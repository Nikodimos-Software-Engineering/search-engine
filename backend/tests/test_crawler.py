import pytest
from crawler import normalize_url, RobotsCompliantCrawler
from unittest.mock import AsyncMock, Mock


class TestNormalizeUrl:

    def test_strips_trailing_slash(self):
        assert normalize_url("https://example.com/page/") == "https://example.com/page"

    def test_lowercases_scheme(self):
        assert normalize_url("HTTP://EXAMPLE.COM/page") == "http://example.com/page"

    def test_handles_scheme_and_trailing_slash_together(self):
        assert normalize_url("HTTP://Example.COM/Page/") == "http://example.com/Page"

    def test_treats_root_with_and_without_slash_as_same(self):
        assert normalize_url("http://example.com/") == normalize_url("http://example.com")

    def test_preserves_query_params(self):
        assert normalize_url("https://example.com/page?a=1&b=2") == "https://example.com/page?a=1&b=2"


class TestCrawlerDedup:

    @pytest.mark.asyncio
    async def test_deduplicates_normalized_urls(self):
        crawler = RobotsCompliantCrawler()

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>test</body></html>"
        mock_response.url = "http://example.com/page"
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        result1 = await crawler.fetch_page("http://example.com/page/", mock_client)
        result2 = await crawler.fetch_page("http://example.com/page", mock_client)
        result3 = await crawler.fetch_page("HTTP://example.com/page/", mock_client)

        assert result1 is not None
        assert result2 is None
        assert result3 is None
