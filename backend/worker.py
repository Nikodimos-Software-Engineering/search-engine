import asyncio
import time
import os
from database import SessionLocal, CrawlJob
from crawler import RobotsCompliantCrawler
from indexer import SearchIndex

INDEX_FILE = "data/search_index.json"

os.makedirs("data", exist_ok=True)


async def process_job(job):
    crawler = RobotsCompliantCrawler()
    documents = await crawler.crawl_site(job.url, job.max_pages)

    index = SearchIndex()
    index.load_from_db()
    index.add_documents(documents)
    index.build_index()
    index.save(INDEX_FILE)

    return len(documents)


def run_worker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    print("Worker started, polling for crawl jobs...")
    while True:
        db = SessionLocal()
        try:
            job = (
                db.query(CrawlJob)
                .filter_by(status="pending")
                .order_by(CrawlJob.created_at)
                .first()
            )
            if job:
                job.status = "running"
                db.commit()
                print(f"Processing job {job.id}: crawl {job.url}")
                try:
                    pages = loop.run_until_complete(process_job(job))
                    job.status = "completed"
                    job.pages_crawled = pages
                    db.commit()
                    print(
                        f"Job {job.id} complete: {pages} pages indexed. "
                        f"Total index saved to {INDEX_FILE}"
                    )
                except Exception as e:
                    job.status = "failed"
                    job.error = str(e)
                    db.commit()
                    print(f"Job {job.id} failed: {e}")
            else:
                time.sleep(5)
        finally:
            db.close()


if __name__ == "__main__":
    run_worker()
