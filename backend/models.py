from sqlalchemy import Column, Integer, String, Text, JSON
from database import Base

class Work(Base):
    __tablename__ = "works"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    tags = Column(JSON, default=list)
    wordCount = Column(String(50), default="0字")
    status = Column(String(50), default="草稿")
    updatedAt = Column(String(50))
    createdAt = Column(String(50))
    cover = Column(String(255))
    synopsis = Column(Text, default="")
    
    # Complex JSON structures
    characters = Column(JSON, default=list)
    worldview = Column(JSON, default=list)
    terms = Column(JSON, default=list)
    timeline = Column(JSON, default=list)
    plotNodes = Column(JSON, default=list)
    chapters = Column(JSON, default=list)
    rules = Column(JSON, default=list)
    threads = Column(JSON, default=list)
    materials = Column(JSON, default=list)
    activities = Column(JSON, default=list)
    comicProduction = Column(JSON, default=dict)


class WorkRevision(Base):
    __tablename__ = "work_revisions"
    id = Column(Integer, primary_key=True)
    work_id = Column(Integer, index=True, nullable=False)
    created_at = Column(String(50), nullable=False)
    data = Column(JSON, nullable=False)

