import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

# Render uses postgres://, SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    url = Column(String(500), unique=True, index=True)
    title = Column(String(500))
    content = Column(Text)
    domain = Column(String(100), index=True)
    crawled_at = Column(DateTime, default=datetime.utcnow)
    word_count = Column(Integer)


class SearchLog(Base):
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True)
    query = Column(String(200), index=True)
    results_count = Column(Integer)
    response_time_ms = Column(Float)
    searched_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, index=True)
    role = Column(String(20), default="user")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
