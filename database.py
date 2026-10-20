import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./infinity_erp.db")

# Fix URL scheme for SQLAlchemy + psycopg2
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # 1. Force SSL by appending it directly to the URL parameters
    url_parts = urlparse(DATABASE_URL)
    query = parse_qs(url_parts.query)
    query['sslmode'] = ['require']
    new_query = urlencode(query, doseq=True)
    DATABASE_URL = urlunparse(url_parts._replace(query=new_query))
    
    # 2. pool_pre_ping=True fixes the "EOF detected" error. 
    # It tests the connection before using it, preventing crashes from idle drops.
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
