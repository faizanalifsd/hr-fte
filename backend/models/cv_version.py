"""
CVVersion Model - Represents optimized CV versions for specific jobs.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime
from . import Base


class CVVersion(Base):
    """
    CVVersion entity - stores optimized CV variants.

    As per execution_plan.md Phase 6:
    - Generated per job by Ollama (mistral:7b-instruct-q4)
    - Tailored to match job keywords
    - No fabrication allowed
    - Stored for audit trail
    """
    __tablename__ = "cv_versions"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign Keys
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True, index=True)

    # Version Info
    version_name = Column(String(255), nullable=False)
    is_master = Column(Integer, default=0)  # 1 if master/original CV, 0 if job-specific

    # CV Content
    content_markdown = Column(Text, nullable=False)
    content_pdf = Column(LargeBinary, nullable=True)  # Store PDF binary

    # Optimization Details
    keyword_match_score = Column(Integer, nullable=True)  # Percentage 0-100
    optimization_notes = Column(Text, nullable=True)
    suggested_improvements = Column(Text, nullable=True)  # JSON as text

    # File Storage
    file_path = Column(String(500), nullable=True)  # Path to stored PDF file
    file_name = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    mission = relationship("Mission", back_populates="cv_versions")
    job = relationship("Job", back_populates="cv_versions")
    application_records = relationship("ApplicationRecord", back_populates="cv_version")

    def __repr__(self):
        cv_type = "Master" if self.is_master else "Optimized"
        return f"<CVVersion(id={self.id}, name='{self.version_name}', type={cv_type})>"
