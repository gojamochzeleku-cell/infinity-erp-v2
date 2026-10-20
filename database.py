import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./infinity_erp.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    url_parts = urlparse(DATABASE_URL)
    query = parse_qs(url_parts.query)
    query['sslmode'] = ['require']
    DATABASE_URL = urlunparse(url_parts._replace(query=urlencode(query, doseq=True)))
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_timeout=30)

    # ☁️ WARM-UP: Gently wake the sleeping cloud database with retries
    for attempt in range(1, 8):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ Cloud database is awake and connected.")
            break
        except Exception as e:
            print(f"⏳ Waking database... attempt {attempt}/7 ({type(e).__name__})")
            time.sleep(4)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
