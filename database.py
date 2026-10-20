import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./infinity_erp.db")

# Ensure correct driver
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Fix Neon-specific SSL and channel_binding issues
    url_parts = urlparse(DATABASE_URL)
    query = parse_qs(url_parts.query)
    query['sslmode'] = ['require']
    query['channel_binding'] = ['disable'] # Crucial fix for psycopg2 on Neon
    DATABASE_URL = urlunparse(url_parts._replace(query=urlencode(query, doseq=True)))
    
    # pool_pre_ping=True automatically tests connections before use.
    # NO manual warm-up at import time to prevent Gunicorn fork connection corruption!
    engine = create_engine(
        DATABASE_URL, 
        pool_pre_ping=True, 
        pool_size=5, 
        max_overflow=10
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
