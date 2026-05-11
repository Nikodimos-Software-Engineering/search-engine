# Educational Search Engine

A search engine for programming documentation with TF-IDF ranking, built with FastAPI and PostgreSQL.

## Features

- **Web Crawler**: Respects robots.txt, async crawling with httpx
- **TF-IDF Search**: Custom implementation with fuzzy matching ("dict" finds "dictionary")
- **JWT Auth**: Role-based access - public search vs admin crawl controls
- **PostgreSQL**: Persistent storage with SQLAlchemy
- **Analytics**: Search query logging with response times

## Tech Stack

- Backend: FastAPI, SQLAlchemy, NumPy, python-jose
- Frontend: Vanilla HTML/CSS/JS
- Database: PostgreSQL

## API Endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| `POST /api/search` | Public | Search indexed documents |
| `GET /api/stats` | Public | Get index statistics |
| `POST /api/auth/login` | Public | Admin login (returns JWT) |
| `POST /api/crawl` | Admin JWT | Start crawling a site |
| `DELETE /api/index` | Admin JWT | Clear the index |
| `GET /api/admin/stats` | Admin JWT | Detailed admin stats |

## Deployment Link

https://search-engine-jcwt.onrender.com

## Admin Credentials

- Username: `admin`
- Password: `admin123`

## Local Setup

```bash
cd backend
pip install -r requirements.txt

# Linux/Mac
export DATABASE_URL="postgresql://user:pass@localhost:5432/search_engine"
# Windows (CMD)
set DATABASE_URL=postgresql://user:pass@localhost:5432/search_engine
# Windows (PowerShell)
$env:DATABASE_URL="postgresql://user:pass@localhost:5432/search_engine"

uvicorn main:app --host 0.0.0.0 --port 8000
