import os
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Table, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import sqlcipher3
from datetime import datetime

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
    filename = Column(String, nullable=False) # Original filename (encrypted in blob, but we keep a searchable name here, maybe pseudonymized? Wait, the user wants the DB to be encrypted so we can store plaintext here)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    category = relationship("Category", back_populates="files")
    tags = relationship("Tag", secondary=file_tag_association, back_populates="files")

class DatabaseManager:
    def __init__(self, db_path: str, password: str):
        # We must use URL encoding or absolute paths properly for sqlite+pysqlcipher
        # Using a direct connection string with the module parameter
        db_url = f"sqlite+pysqlcipher://:{password}@/{os.path.abspath(db_path)}"
        
        self.engine = create_engine(
            db_url,
            module=sqlcipher3
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def init_db(self):
        """Creates tables if they don't exist."""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self):
        """Returns a new database session."""
        return self.SessionLocal()
