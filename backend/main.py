import asyncio
import os
import threading
import time

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import init_db, get_db, SessionLocal, Document, SearchLog, CrawlJob, IndexData

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
last_index_updated_at = None


def reload_index_if_needed(db):
    global search_index, last_index_updated_at
    entry = db.query(IndexData).first()
    if entry and entry.updated_at != last_index_updated_at:
        new_index = SearchIndex()
        new_index.load(db)
        search_index = new_index
        last_index_updated_at = entry.updated_at
        print(f"Index reloaded from database ({len(search_index.documents)} docs)")


async def _process_job(job):
    crawler_worker = RobotsCompliantCrawler()
    documents = await crawler_worker.crawl_site(job.url, job.max_pages)
    index = SearchIndex()
    index.load_from_db()
    index.add_documents(documents)
    index.build_index()
    index.save()
    return len(documents)


def reset_stuck_jobs():
    db = SessionLocal()
    try:
        stuck = db.query(CrawlJob).filter_by(status="running").all()
        for job in stuck:
            job.status = "pending"
            job.error = "Reset - server restarted while running"
        db.commit()
        if stuck:
            print(f"Reset {len(stuck)} stuck crawl jobs to pending")
    finally:
        db.close()


def start_worker_thread():
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        print("Worker thread started, polling for crawl jobs...")
        while True:
            db = SessionLocal()
            try:
                job = db.query(CrawlJob).filter_by(status="pending").order_by(CrawlJob.created_at).first()
                if job:
                    job.status = "running"
                    db.commit()
                    print(f"Worker processing job {job.id}: crawl {job.url}")
                    try:
                        pages = loop.run_until_complete(_process_job(job))
                        job.status = "completed"
                        job.pages_crawled = pages
                        db.commit()
                        print(f"Job {job.id} complete: {pages} pages indexed")
                    except Exception as e:
                        job.status = "failed"
                        job.error = str(e)
                        db.commit()
                        print(f"Job {job.id} failed: {e}")
                else:
                    time.sleep(5)
            finally:
                db.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


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
    global last_index_updated_at
    init_db()
    reset_stuck_jobs()
    db = SessionLocal()
    try:
        entry = db.query(IndexData).first()
        if entry and entry.data:
            last_index_updated_at = entry.updated_at
            search_index.load(db)
            print(f"Loaded index from database ({len(search_index.documents)} docs)")
    finally:
        db.close()
    start_worker_thread()


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
    reload_index_if_needed(db)
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
    reload_index_if_needed(db)
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
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    url = str(request.url)

    if not crawler.can_fetch(url):
        raise HTTPException(status_code=403, detail="Crawling blocked by robots.txt")

    job = CrawlJob(url=url, max_pages=request.max_pages, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)

    return {
        "job_id": job.id,
        "message": f"Crawl job created for {url}",
        "status": "pending"
    }


@app.delete("/api/index")
async def clear_index(db: Session = Depends(get_db), admin: dict = Depends(get_current_admin)):
    global search_index
    search_index = SearchIndex()
    db.query(Document).delete()
    db.query(SearchLog).delete()
    db.query(IndexData).delete()
    db.query(CrawlJob).filter(CrawlJob.status == "pending").delete()
    db.commit()
    return {"message": "Index cleared"}


@app.get("/api/crawl/status/{job_id}")
async def get_crawl_status(job_id: int, db: Session = Depends(get_db)):
    job = db.query(CrawlJob).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.id,
        "url": job.url,
        "status": job.status,
        "pages_crawled": job.pages_crawled,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None
    }


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
        "index_in_db": db.query(IndexData).count() > 0
    }


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
