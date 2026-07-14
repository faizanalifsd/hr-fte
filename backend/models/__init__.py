"""
Database models package for AI Job Application System.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Base class for all models
Base = declarative_base()

# Database engine (will be initialized from config)
engine = None
SessionLocal = None


def init_db(database_url: str):
    """Initialize database connection."""
    global engine, SessionLocal

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False  # Set to True for SQL debugging
    )

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Import all models to ensure they're registered
    from .mission import Mission
    from .job import Job
    from .cv_version import CVVersion
    from .email_draft import EmailDraft
    from .application_record import ApplicationRecord
    from .execution_state import ExecutionState
    from .audit_log import AuditLog

    # Create all tables
    Base.metadata.create_all(bind=engine)

    return engine


def get_db():
    """Get database session. Use as dependency in FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# EXPORT ALL MODELS AND ENUMS
# ============================================================

from .mission import Mission, MissionStatus
from .job import Job, JobStatus
from .cv_version import CVVersion
from .email_draft import EmailDraft, EmailStatus
from .application_record import ApplicationRecord, ApplicationOutcome
from .execution_state import ExecutionState, ExecutionPhase, ExecutionStatus
from .audit_log import AuditLog, ActionType, LogLevel

__all__ = [
    # Database helpers
    "Base", "init_db", "get_db", "SessionLocal",
    # Models
    "Mission", "Job", "CVVersion", "EmailDraft",
    "ApplicationRecord", "ExecutionState", "AuditLog",
    # Enums
    "MissionStatus", "JobStatus", "EmailStatus", "ApplicationOutcome",
    "ExecutionPhase", "ExecutionStatus", "ActionType", "LogLevel",
]
