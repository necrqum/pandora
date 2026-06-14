import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Table, ForeignKey, text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.exc import OperationalError, IntegrityError as SAIntegrityError
from sqlalchemy import event
import sqlcipher3
from datetime import datetime

from .exceptions import DatabaseConnectionError, DatabaseIntegrityError, DatabaseError

logger = logging.getLogger("pandora.database")

Base = declarative_base()

# Many-to-many association table for files and tags
file_tag_association = Table(
    'file_tag',
    Base.metadata,
    Column('file_id', String, ForeignKey('files.id')),
    Column('tag_id', Integer, ForeignKey('tags.id'))
)

class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    
    files = relationship("File", back_populates="category")

class Tag(Base):
    __tablename__ = 'tags'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    
    files = relationship("File", secondary=file_tag_association, back_populates="tags")

class File(Base):
    __tablename__ = 'files'
    id = Column(String, primary_key=True) # UUID
    filename = Column(String, nullable=False) # Original filename
    size = Column(Integer, default=0) # Unencrypted size in bytes
    duration = Column(Integer, nullable=True) # Duration in seconds
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=True)
    thumbnail_data = Column(String, nullable=True) # Base64 encoded thumbnail
    added_at = Column(DateTime, default=datetime.utcnow) # When added to Pandora
    metadata_created_at = Column(DateTime, nullable=True) # From file metadata
    is_favorite = Column(Integer, default=0) # 0 for False, 1 for True (SQLite compatible)
    notes = Column(String, nullable=True) # Personal notes
    
    category = relationship("Category", back_populates="files")
    tags = relationship("Tag", secondary=file_tag_association, back_populates="files")

class DatabaseManager:
    def __init__(self, db_path: str, password: str):
        # We must use URL encoding or absolute paths properly for sqlite+pysqlcipher
        # Using a direct connection string with the module parameter
        db_url = f"sqlite+pysqlcipher://:{password}@/{os.path.abspath(db_path)}"

        try:
            from sqlalchemy.pool import NullPool
            self.engine = create_engine(
                db_url,
                module=sqlcipher3,
                poolclass=NullPool,
                connect_args={"check_same_thread": False}
            )
            
            # Enable WAL mode and busy timeout for better concurrency
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=30000") # 30 seconds
                cursor.execute("PRAGMA cache_size=-64000") # 64MB cache
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.close()

            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        except Exception as exc:
            logger.error("Failed to create database engine for %s: %s", db_path, exc)
            raise DatabaseConnectionError(
                f"Cannot connect to database at {db_path}: {exc}"
            ) from exc

    def init_db(self):
        """Creates tables if they don't exist.

        Raises:
            DatabaseConnectionError: If the schema cannot be created.
        """
        try:
            Base.metadata.create_all(bind=self.engine)
            # Ensure new columns exist on older databases
            with self.engine.begin() as conn:
                try:
                    conn.execute(text("ALTER TABLE files ADD COLUMN thumbnail_data VARCHAR"))
                except OperationalError: pass
                try:
                    conn.execute(text("ALTER TABLE files ADD COLUMN duration INTEGER"))
                except OperationalError: pass
                try:
                    # Migration: rename created_at to added_at if it exists
                    conn.execute(text("ALTER TABLE files RENAME COLUMN created_at TO added_at"))
                except OperationalError: pass
                try:
                    conn.execute(text("ALTER TABLE files ADD COLUMN metadata_created_at DATETIME"))
                except OperationalError: pass
                try:
                    conn.execute(text("ALTER TABLE files ADD COLUMN is_favorite INTEGER DEFAULT 0"))
                except OperationalError: pass
                try:
                    conn.execute(text("ALTER TABLE files ADD COLUMN notes TEXT"))
                except OperationalError: pass
        except OperationalError as exc:
            logger.error("Failed to initialize database schema: %s", exc)
            raise DatabaseConnectionError(
                f"Failed to create database tables: {exc}"
            ) from exc

    def get_session(self):
        """Returns a new database session.

        .. deprecated:: Use :meth:`session_scope` instead for automatic
           commit / rollback handling.
        """
        return self.SessionLocal()

    @contextmanager
    def session_scope(self):
        """Context manager that yields a DB session with auto-commit/rollback.

        Usage::

            with db.session_scope() as session:
                session.add(obj)
                # auto-commits on success, auto-rolls-back on exception

        Raises:
            DatabaseIntegrityError: On constraint violations.
            DatabaseError: On any other database failure.
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except SAIntegrityError as exc:
            session.rollback()
            logger.error("Database integrity error: %s", exc)
            raise DatabaseIntegrityError(
                f"Data integrity violation: {exc}"
            ) from exc
        except OperationalError as exc:
            session.rollback()
            logger.error("Database operational error: %s", exc)
            raise DatabaseConnectionError(
                f"Database operation failed: {exc}"
            ) from exc
        except Exception as exc:
            session.rollback()
            logger.error("Unexpected database error: %s", exc)
            raise DatabaseError(
                f"Unexpected database error: {exc}"
            ) from exc
        finally:
            session.close()

    def verify_password(self) -> bool:
        """Attempts a read to verify the encryption password is correct.

        Returns:
            ``True`` if the password is valid.

        Raises:
            DatabaseConnectionError: If the password is wrong or the DB is corrupt.
        """
        from sqlalchemy import text
        try:
            with self.session_scope() as session:
                session.execute(text("SELECT count(*) FROM sqlite_master")).fetchall()
            return True
        except Exception as exc:
            raise DatabaseConnectionError(
                "Database password verification failed — wrong password or corrupt database."
            ) from exc
