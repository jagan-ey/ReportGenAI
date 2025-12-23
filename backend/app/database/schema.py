from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class PredefinedQueries(Base):
    """PREDEFINED_QUERIES - Store predefined queries in database"""
    __tablename__ = 'predefined_queries'
    
    QUERY_ID = Column(Integer, primary_key=True, autoincrement=True)
    QUERY_KEY = Column(String(50), unique=True, nullable=False)  # e.g., "rekyc_freeze"
    QUESTION = Column(Text, nullable=False)  # The question text (used for matching)
    SQL_QUERY = Column(Text, nullable=False)  # The SQL query
    DESCRIPTION = Column(String(500))  # Description of what the query does
    IS_ACTIVE = Column(Boolean, default=True)  # Enable/disable query
    CREATED_DATE = Column(Date)
    UPDATED_DATE = Column(Date)
    CREATED_BY = Column(String(50))
    UPDATED_BY = Column(String(50))

