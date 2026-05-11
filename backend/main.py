from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import init_db, get_db, Document, SearchLog
import os
import time

from crawler import RobotsCompliantCrawler
from indexer import SearchIndex
from auth import create_access_token, get_current_user, get_current_admin, ADMIN_USER


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
INDEX_FILE = "data/search_index.json"


class CrawlRequest(BaseModel):
    url: HttpUrl
    max_pages: int = 50

class SearchRequest(BaseModel):
    query: str
    top_k: int = 10

class LoginRequest(BaseModel):
    username: str
    password: str


@app.on_event("startup")
async def load_existing_index():
    init_db()
    if os.path.exists(INDEX_FILE):
        search_index.load(INDEX_FILE)
        print(f"Loaded existing index with {len(search_index.documents)} documents")


@app.head("/")
async def root_head():
    return {}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"))


@app.post("/api/search")
async def search(request: SearchRequest, db: Session = Depends(get_db)):
    if not search_index.is_built:
        raise HTTPException(status_code=400, detail="Index not built yet. Crawl a site first.")
    if not request.query.strip():
        return []
    
    start_time = time.time()
    results = search_index.search(request.query, request.top_k)
    elapsed_ms = (time.time() - start_time) * 1000
    
    log = SearchLog(query=request.query, results_count=len(results), response_time_ms=elapsed_ms)
    db.add(log)
    db.commit()
    return results


@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    total_docs = db.query(Document).count()
    total_searches = db.query(SearchLog).count()
    avg_time = db.query(func.avg(SearchLog.response_time_ms)).scalar()
    
    return {
        "total_documents": total_docs,
        "index_built": search_index.is_built,
        "vocabulary_size": len(search_index.vocabulary) if search_index.vocabulary else 0,
        "total_searches": total_searches or 0,
        "avg_response_time_ms": round(avg_time, 2) if avg_time else 0
    }


@app.post("/api/auth/login")
async def login(request: LoginRequest):
    if request.username == ADMIN_USER["username"] and request.password == ADMIN_USER["password"]:
        token = create_access_token({
            "username": ADMIN_USER["username"],
            "role": ADMIN_USER["role"]
        })
        return {"access_token": token, "token_type": "bearer", "role": "admin"}
    
    raise HTTPException(status_code=401, detail="Invalid username or password")


@app.get("/api/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {"username": user.get("username"), "role": user.get("role")}


@app.post("/api/crawl")
async def crawl_website(
    request: CrawlRequest, 
    background_tasks: BackgroundTasks,
    admin: dict = Depends(get_current_admin)
):
    url = str(request.url)
    
    if not crawler.can_fetch(url):
        raise HTTPException(status_code=403, detail="Crawling blocked by robots.txt")
    
    background_tasks.add_task(perform_crawl, url, request.max_pages)
    
    return {
        "message": f"Crawling started for {url}",
        "pages_crawled": 0,
        "status": "in_progress"
    }


@app.delete("/api/index")
async def clear_index(db: Session = Depends(get_db), admin: dict = Depends(get_current_admin)):
    global search_index
    search_index = SearchIndex()
    db.query(Document).delete()
    db.query(SearchLog).delete()
    db.commit()
    if os.path.exists(INDEX_FILE):
        os.remove(INDEX_FILE)
    return {"message": "Index cleared"}


@app.get("/api/admin/stats")
async def get_admin_stats(db: Session = Depends(get_db), admin: dict = Depends(get_current_admin)):
    total_docs = db.query(Document).count()
    total_searches = db.query(SearchLog).count()
    avg_time = db.query(func.avg(SearchLog.response_time_ms)).scalar()
    
    return {
        "total_documents": total_docs,
        "index_built": search_index.is_built,
        "vocabulary_size": len(search_index.vocabulary) if search_index.vocabulary else 0,
        "total_searches": total_searches or 0,
        "avg_response_time_ms": round(avg_time, 2) if avg_time else 0,
        "index_file_exists": os.path.exists(INDEX_FILE)
    }


async def perform_crawl(url, max_pages):
    global search_index
    new_crawler = RobotsCompliantCrawler()
    documents = await new_crawler.crawl_site(url, max_pages)
    search_index.add_documents(documents)
    search_index.build_index()
    search_index.save(INDEX_FILE)
    print(f"Crawl complete: {len(documents)} pages indexed. Total: {len(search_index.documents)}")


@app.get("/admin", response_class=HTMLResponse)
async def serve_admin_login():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "frontend", "admin", "login.html"))


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def serve_admin_dashboard():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "frontend", "admin", "dashboard.html"))


frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
