"""
Mission API Routes - CRUD operations for missions.
"""

import threading
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ..models import Mission, MissionStatus, AuditLog, get_db
from .. import models as _models          # accessed at call-time so SessionLocal is not None
from ..services.orchestrator import ApplicationOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/missions", tags=["missions"])


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class MissionCreate(BaseModel):
    """Request model for creating a mission."""
    user_input: str


class MissionResponse(BaseModel):
    """Response model for mission data."""
    id: int
    target_role: str
    target_count: int
    progress_count: int
    status: str
    time_constraint_days: Optional[int]
    location_preference: Optional[str]
    job_type: Optional[str]
    daily_application_limit: int
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class WorkflowExecuteRequest(BaseModel):
    """Request model for executing full workflow."""
    cv_text: str
    cv_file_path: Optional[str] = None
    auto_approve: bool = False  # TESTING ONLY


# ============================================================
# MISSION ENDPOINTS
# ============================================================

@router.post("/", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
def create_mission(
    request: MissionCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new job application mission.

    Phase 1: Mission Initialization
    """
    try:
        orchestrator = ApplicationOrchestrator(db)
        mission = orchestrator.create_mission(request.user_input)

        return MissionResponse(
            id=mission.id,
            target_role=mission.target_role,
            target_count=mission.target_count,
            progress_count=mission.progress_count,
            status=mission.status.value,
            time_constraint_days=mission.time_constraint_days,
            location_preference=mission.location_preference,
            job_type=mission.job_type,
            daily_application_limit=mission.daily_application_limit,
            created_at=mission.created_at,
            completed_at=mission.completed_at
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mission creation failed: {str(e)}"
        )


@router.get("/", response_model=List[MissionResponse])
def list_missions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all missions with pagination.
    """
    missions = db.query(Mission).offset(skip).limit(limit).all()

    return [
        MissionResponse(
            id=m.id,
            target_role=m.target_role,
            target_count=m.target_count,
            progress_count=m.progress_count,
            status=m.status.value,
            time_constraint_days=m.time_constraint_days,
            location_preference=m.location_preference,
            job_type=m.job_type,
            daily_application_limit=m.daily_application_limit,
            created_at=m.created_at,
            completed_at=m.completed_at
        )
        for m in missions
    ]


@router.get("/{mission_id}", response_model=MissionResponse)
def get_mission(
    mission_id: int,
    db: Session = Depends(get_db)
):
    """
    Get mission by ID.
    """
    mission = db.query(Mission).filter(Mission.id == mission_id).first()

    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission {mission_id} not found"
        )

    return MissionResponse(
        id=mission.id,
        target_role=mission.target_role,
        target_count=mission.target_count,
        progress_count=mission.progress_count,
        status=mission.status.value,
        time_constraint_days=mission.time_constraint_days,
        location_preference=mission.location_preference,
        job_type=mission.job_type,
        daily_application_limit=mission.daily_application_limit,
        created_at=mission.created_at,
        completed_at=mission.completed_at
    )


def _run_workflow_background(
    mission_id: int,
    cv_text: str,
    cv_file_path: Optional[str],
    auto_approve: bool,
) -> None:
    """Run the full workflow in a background thread with its own DB session."""
    db = _models.SessionLocal()   # read at call-time, after init_db() has run
    try:
        orchestrator = ApplicationOrchestrator(db)
        orchestrator.execute_full_workflow(
            mission_id=mission_id,
            cv_text=cv_text,
            cv_file_path=cv_file_path,
            auto_approve=auto_approve,
        )
    except Exception as e:
        logger.error(f"Background workflow failed for mission {mission_id}: {e}")
    finally:
        db.close()


@router.post("/{mission_id}/execute", status_code=status.HTTP_202_ACCEPTED)
def execute_workflow(
    mission_id: int,
    request: WorkflowExecuteRequest,
    db: Session = Depends(get_db)
):
    """
    Start the full 12-phase workflow in a background thread.

    Returns 202 immediately — poll GET /api/missions/{id} and
    GET /api/missions/{id}/audit for live progress.
    """
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission {mission_id} not found"
        )

    thread = threading.Thread(
        target=_run_workflow_background,
        args=(mission_id, request.cv_text, request.cv_file_path, request.auto_approve),
        daemon=True,
    )
    thread.start()

    return {
        "message": "Workflow started — poll /api/missions/{id}/audit for progress",
        "mission_id": mission_id,
        "jobs_scraped": 0,
        "jobs_matched": 0,
        "pending_approvals": 0,
    }


@router.get("/{mission_id}/audit")
def get_mission_audit_log(
    mission_id: int,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get audit log entries for a mission.

    Phase 10: Evidence & Audit
    """
    mission = db.query(Mission).filter(Mission.id == mission_id).first()
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission {mission_id} not found"
        )

    logs = (
        db.query(AuditLog)
        .filter(AuditLog.mission_id == mission_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": log.id,
            "mission_id": log.mission_id,
            "timestamp": log.timestamp.isoformat(),
            "level": log.level.value,
            "action_type": log.action_type.value,
            "agent_name": log.agent_name,
            "output_summary": log.output_summary,
            "status": log.status,
            "error_message": log.error_message,
            "job_id": log.job_id,
        }
        for log in logs
    ]


@router.delete("/{mission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mission(
    mission_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a mission and all related data.
    """
    mission = db.query(Mission).filter(Mission.id == mission_id).first()

    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission {mission_id} not found"
        )

    db.delete(mission)
    db.commit()

    return None
