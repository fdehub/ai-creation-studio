from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from settings import DATA_DIR

SQLALCHEMY_DATABASE_URL = "sqlite:///" + (DATA_DIR / "ai_novel.db").as_posix()

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def upgrade_schema():
    """Add production metadata without rebuilding or replacing an existing DB."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if not inspector.has_table('works'): return
    if 'comicProduction' in {column['name'] for column in inspector.get_columns('works')}: return
    # SQLite's backup API obtains a consistent backup, including WAL contents.
    import sqlite3
    from contextlib import closing
    from datetime import datetime, timezone
    backup_dir = DATA_DIR / 'backups'
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / ('before-comic-production-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.db')
    with closing(sqlite3.connect(DATA_DIR / 'ai_novel.db')) as source, closing(sqlite3.connect(backup)) as destination:
        source.backup(destination)
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE works ADD COLUMN "comicProduction" JSON NOT NULL DEFAULT \'{}\''))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
