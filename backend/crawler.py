import httpx
import time
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import asyncio


class RobotsCompliantCrawler:
    def __init__(self, respect_crawl_delay=True, default_delay=1.0):
        self.respect_delay = respect_crawl_delay
        self.default_delay = default_delay
        self.robot_parsers = {}
        self.last_fetch_time = {}
        self.visited_urls = set()

    def get_robot_parser(self, base_url):
        domain = urlparse(base_url).netloc
        if domain not in self.robot_parsers:
            robots_url = urljoin(base_url, "/robots.txt")
            parser = RobotFileParser()
            parser.set_url(robots_url)
            try:
                parser.read()
                self.robot_parsers[domain] = parser
            except Exception as e:
                print(f"Could not fetch robots.txt: {e}")
                self.robot_parsers[domain] = None
        return self.robot_parsers[domain]

    def can_fetch(self, url, user_agent="*"):
        parser = self.get_robot_parser(url)
        if parser is None:
            return True
        return parser.can_fetch(user_agent, url)

    async def respect_crawl_delay(self, base_url):
        if not self.respect_delay:
            return
        domain = urlparse(base_url).netloc
        delay = self.default_delay
        last_time = self.last_fetch_time.get(domain, 0)
        elapsed = time.time() - last_time
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self.last_fetch_time[domain] = time.time()

    async def fetch_page(self, url, client):
        if url in self.visited_urls:
            return None
        if not self.can_fetch(url):
            print(f"Blocked by robots.txt: {url}")
            return None
        await self.respect_crawl_delay(url)
        try:
            response = await client.get(url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            self.visited_urls.add(url)
            return {"url": str(response.url), "html": response.text, "status": response.status_code}
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def extract_content(self, html, url):
        soup = BeautifulSoup(html, 'lxml')
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        title = soup.find('title')
        title_text = title.get_text(strip=True) if title else ""
        main_content = soup.find('article') or soup.find('main') or soup.find('body')
        text = main_content.get_text(separator=' ', strip=True) if main_content else ""
        text = ' '.join(text.split())
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(url, href)
            if urlparse(full_url).netloc == urlparse(url).netloc:
                links.append(full_url)
        return {"url": url, "title": title_text, "content": text, "links": links}

    async def crawl_site(self, start_url, max_pages=50):
        results = []
        to_visit = [start_url]
        headers = {"User-Agent": "MySearchBot/1.0 (Educational Search Engine)"}
        async with httpx.AsyncClient(headers=headers) as client:
            while to_visit and len(results) < max_pages:
                current_url = to_visit.pop(0)
                page_data = await self.fetch_page(current_url, client)
                if not page_data:
                    continue
                extracted = self.extract_content(page_data["html"], page_data["url"])
                results.append(extracted)
                for link in extracted["links"]:
                    if link not in self.visited_urls and link not in to_visit:
                        to_visit.append(link)
                to_visit = list(dict.fromkeys(to_visit))[:100]
        return results
