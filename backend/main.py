from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, HttpUrl
import os

from crawler import RobotsCompliantCrawler
from indexer import SearchIndex


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

search_index = SearchIndex()
crawler = RobotsCompliantCrawler()
INDEX_FILE = "search_index.json"


class CrawlRequest(BaseModel):
    url: HttpUrl
    max_pages: int = 50

class SearchRequest(BaseModel):
    query: str
    top_k: int = 10


@app.on_event("startup")
async def load_existing_index():
    if os.path.exists(INDEX_FILE):
        search_index.load(INDEX_FILE)
        print(f"Loaded existing index with {len(search_index.documents)} documents")


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DocsSearch</title>
        <link rel="stylesheet" href="/static/styles.css">
    </head>
    <body>
        <div id="app"></div>
        <script src="/static/app.js"></script>
    </body>
    </html>
    """


@app.post("/api/crawl")
async def crawl_website(request: CrawlRequest, background_tasks: BackgroundTasks):
    url = str(request.url)
    
    if not crawler.can_fetch(url):
        raise HTTPException(status_code=403, detail="Crawling blocked by robots.txt")
    
    background_tasks.add_task(perform_crawl, url, request.max_pages)
    
    return {
        "message": f"Crawling started for {url}",
        "pages_crawled": 0,
        "status": "in_progress"
    }


async def perform_crawl(url, max_pages):
    global search_index
    
    new_crawler = RobotsCompliantCrawler()
    documents = await new_crawler.crawl_site(url, max_pages)
    
    search_index.add_documents(documents)
    search_index.build_index()
    
    search_index.save(INDEX_FILE)
    
    print(f"Crawl complete: {len(documents)} pages indexed. Total: {len(search_index.documents)}")


@app.post("/api/search")
async def search(request: SearchRequest):
    if not search_index.is_built:
        raise HTTPException(status_code=400, detail="Index not built yet. Crawl a site first.")
    
    if not request.query.strip():
        return []
    
    results = search_index.search(request.query, request.top_k)
    return results


@app.get("/api/stats")
async def get_stats():
    return {
        "total_documents": len(search_index.documents),
        "index_built": search_index.is_built,
        "vocabulary_size": len(search_index.vocabulary) if search_index.vocabulary else 0
    }


@app.delete("/api/index")
async def clear_index():
    global search_index
    search_index = SearchIndex()
    if os.path.exists(INDEX_FILE):
        os.remove(INDEX_FILE)
    return {"message": "Index cleared"}


frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
