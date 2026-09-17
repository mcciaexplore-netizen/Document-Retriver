from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30} if DATABASE_URL.startswith("sqlite") else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def sqlite_pragmas(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def get_db():
    with SessionLocal() as db:
        yield db


def install_search_index(connection):
    if connection.dialect.name == "sqlite":
        connection.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(normalized_content, content='document_chunks', content_rowid='id', tokenize='unicode61')"))
        connection.execute(text("CREATE TRIGGER IF NOT EXISTS records_ai AFTER INSERT ON document_chunks BEGIN INSERT INTO records_fts(rowid,normalized_content) VALUES(new.id,new.normalized_content); END"))
        connection.execute(text("CREATE TRIGGER IF NOT EXISTS records_ad AFTER DELETE ON document_chunks BEGIN INSERT INTO records_fts(records_fts,rowid,normalized_content) VALUES('delete',old.id,old.normalized_content); END"))
        connection.execute(text("CREATE TRIGGER IF NOT EXISTS records_au AFTER UPDATE ON document_chunks BEGIN INSERT INTO records_fts(records_fts,rowid,normalized_content) VALUES('delete',old.id,old.normalized_content); INSERT INTO records_fts(rowid,normalized_content) VALUES(new.id,new.normalized_content); END"))
    else:
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_document_fulltext ON document_chunks USING GIN (to_tsvector('simple', normalized_content))"))


def init_db():
    import models  # noqa: F401
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        install_search_index(connection)
