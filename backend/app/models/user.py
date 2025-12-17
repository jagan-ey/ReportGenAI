"""
User models for authentication and authorization
For POC, we'll use a simple session-based approach
In production, this would integrate with your SSO/AD/LDAP
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from datetime import datetime
from app.database.schema import Base


class User(Base):
    """User model for authentication"""
    __tablename__ = 'users'
    
    USER_ID = Column(Integer, primary_key=True, autoincrement=True)
    USERNAME = Column(String(100), unique=True, nullable=False)
    EMAIL = Column(String(200), unique=True, nullable=False)
    PASSWORD_HASH = Column(String(255), nullable=False)  # Hashed password
    FULL_NAME = Column(String(200))
    ROLE = Column(String(50), default='user')  # user, approver, admin
    DEPARTMENT = Column(String(100))
    IS_ACTIVE = Column(Boolean, default=True)
    CREATED_DATE = Column(DateTime, default=datetime.now)
    LAST_LOGIN = Column(DateTime)
    UPDATED_DATE = Column(DateTime)


class ApprovalRequest(Base):
    """Approval requests table"""
    __tablename__ = 'approval_requests'
    
    APPROVAL_ID = Column(Integer, primary_key=True, autoincrement=True)
    REQUEST_ID = Column(String(50), unique=True, nullable=False)  # e.g., "APPROVAL-20250116123456"
    REQUESTED_BY = Column(String(100))  # Username or user ID
    QUERY = Column(Text, nullable=False)
    QUESTION = Column(Text)
    ROW_COUNT = Column(Integer)
    STATUS = Column(String(20), default='pending')  # pending, approved, rejected
    APPROVER_EMAIL = Column(String(200))
    NOTES = Column(Text)
    CREATED_DATE = Column(DateTime, default=datetime.now)
    APPROVED_DATE = Column(DateTime)
    APPROVED_BY = Column(String(100))


class ScheduledReport(Base):
    """Scheduled reports table"""
    __tablename__ = 'scheduled_reports'
    
    SCHEDULE_ID = Column(Integer, primary_key=True, autoincrement=True)
    SCHEDULE_KEY = Column(String(50), unique=True, nullable=False)  # e.g., "SCHEDULE-20250116123456"
    CREATED_BY = Column(String(100))  # Username or user ID
    QUERY = Column(Text, nullable=False)
    QUESTION = Column(Text)
    SCHEDULE_TYPE = Column(String(20), nullable=False)  # daily, weekly, monthly
    SCHEDULE_TIME = Column(String(10))  # HH:MM format
    RECIPIENTS = Column(Text)  # JSON array of email addresses
    IS_ENABLED = Column(Boolean, default=True)
    LAST_RUN = Column(DateTime)
    NEXT_RUN = Column(DateTime)
    CREATED_DATE = Column(DateTime, default=datetime.now)
    UPDATED_DATE = Column(DateTime)

