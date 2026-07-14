"""
AuditLog Model - Immutable audit trail for all system actions.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from . import Base


class LogLevel(enum.Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ActionType(enum.Enum):
    """Action type enumeration."""
    MISSION_CREATED = "Mission_Created"
    MISSION_UPDATED = "Mission_Updated"
    MISSION_COMPLETED = "Mission_Completed"
    CV_UPLOADED = "CV_Uploaded"
    CV_PARSED = "CV_Parsed"
    CV_OPTIMIZED = "CV_Optimized"
    JOBS_SCRAPED = "Jobs_Scraped"
    JOB_MATCHED = "Job_Matched"
    EMAIL_GENERATED = "Email_Generated"
    EMAIL_APPROVED = "Email_Approved"
    EMAIL_REJECTED = "Email_Rejected"
    EMAIL_SENT = "Email_Sent"
    APPLICATION_SUBMITTED = "Application_Submitted"
    AGENT_INVOKED = "Agent_Invoked"
    MCP_CALLED = "MCP_Called"
    ERROR_OCCURRED = "Error_Occurred"


class AuditLog(Base):
    """
    AuditLog entity - immutable audit trail.

    As per constitution.md Section 6.1:
    Every mission must generate immutable logs.

    Each log entry contains:
    - Timestamp
    - Agent name
    - Input reference
    - Output summary
    - Status (Success / Failed)

    Section 6.3: Logs must be queryable by mission ID
    Section 6.4: Support reproducibility of mission history
    """
    __tablename__ = "audit_logs"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign Key
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=False, index=True)

    # Log Details
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    level = Column(
        Enum(LogLevel),
        default=LogLevel.INFO,
        nullable=False,
        index=True
    )

    action_type = Column(
        Enum(ActionType),
        nullable=False,
        index=True
    )

    # Agent/Actor
    agent_name = Column(String(100), nullable=False, index=True)

    # Context
    input_reference = Column(Text, nullable=True)  # JSON or reference to input
    output_summary = Column(Text, nullable=True)

    # Status
    status = Column(String(50), nullable=False, index=True)  # Success, Failed, Partial

    # Error details (if failed)
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)

    # Additional metadata
    duration_ms = Column(Integer, nullable=True)  # Execution duration in milliseconds
    log_metadata = Column(Text, nullable=True)  # JSON for additional context

    # Related entities
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True, index=True)
    cv_version_id = Column(Integer, ForeignKey("cv_versions.id"), nullable=True)
    email_draft_id = Column(Integer, ForeignKey("email_drafts.id"), nullable=True)

    # IP and user tracking (for security)
    user_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible

    # Relationships
    mission = relationship("Mission", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action_type.value}, status={self.status}, timestamp={self.timestamp})>"

    @staticmethod
    def log_action(
        db_session,
        mission_id: int,
        agent_name: str,
        action_type: ActionType,
        status: str,
        level: LogLevel = LogLevel.INFO,
        input_ref: str = None,
        output_summary: str = None,
        error_message: str = None,
        duration_ms: int = None,
        job_id: int = None,
        cv_version_id: int = None,
        email_draft_id: int = None,
        log_metadata: str = None
    ):
        """
        Helper method to create audit log entries.

        Usage:
            AuditLog.log_action(
                db, mission_id=1, agent_name="cv_parser",
                action_type=ActionType.CV_PARSED, status="Success"
            )
        """
        log_entry = AuditLog(
            mission_id=mission_id,
            level=level,
            action_type=action_type,
            agent_name=agent_name,
            input_reference=input_ref,
            output_summary=output_summary,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
            job_id=job_id,
            cv_version_id=cv_version_id,
            email_draft_id=email_draft_id,
            log_metadata=log_metadata
        )
        db_session.add(log_entry)
        db_session.commit()
        return log_entry
