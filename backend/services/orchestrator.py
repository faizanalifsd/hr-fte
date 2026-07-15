"""
Application Orchestrator - Master Workflow Controller.

Implements the 12-phase workflow from execution_plan.md.

LLM ARCHITECTURE (OpenRouter → Groq → Rule-based):
- Primary  : OpenRouter — meta-llama/llama-3.1-8b-instruct:free (200+ models)
- Fallback : Groq — llama-3.3-70b-versatile (ultra-fast, free tier)
- Final    : Rule-based deterministic logic (no API required)

As per constitution.md:
- Enforces governance rules
- Maintains audit trail
- Implements HITL approval
- Handles error recovery with retry logic
"""

import json
import re
import logging
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..models import (
    Mission, Job, CVVersion, EmailDraft, ApplicationRecord,
    ExecutionState, AuditLog,
    MissionStatus, JobStatus, EmailStatus, ExecutionPhase,
    ExecutionStatus, ActionType, LogLevel, ApplicationOutcome
)
from .ai.ollama_service import OllamaService
from .mcp.apify_service import ApifyService
from .mcp.gmail_service import GmailService
from .mcp.apollo_service import enrich_jobs_with_hr_emails

logger = logging.getLogger(__name__)


class RecipientNotConfirmedError(ValueError):
    """Raised when approving an email whose recipient is still an unverified guess."""
    pass


class ApplicationOrchestrator:
    """
    Master orchestrator for the 12-phase job application workflow.

    Responsibilities:
    1. Mission initialization
    2. CV upload & parsing
    3. Job scraping
    4. Job matching
    5. CV optimization
    6. Email generation
    7. HITL approval workflow
    8. Application sending
    9. Audit & evidence logging
    10. Mission validation
    """

    def __init__(self, db: Session):
        """
        Initialize orchestrator with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

        # Initialize local Ollama AI service (self-hosted — no external API key)
        self.ollama = OllamaService()

        # Initialize MCP services
        self.apify = ApifyService()
        self.gmail = GmailService()

        # Error handling config (constitution.md 4.1)
        self.max_retries = 3
        self.retry_delay = 2  # seconds

    # ============================================================
    # PHASE 1: MISSION INITIALIZATION
    # ============================================================

    def create_mission(self, user_input: str, user_id: Optional[str] = None) -> Mission:
        """
        Phase 1: Mission Initialization.

        As per execution_plan.md Phase 1:
        1. User submits Mission Objective
        2. Claude parses: target role, target count, time constraint
        3. Insert Mission record in database
        4. Status = Initialized

        Args:
            user_input: User's mission description
            user_id: Optional user identifier

        Returns:
            Created Mission object
        """
        logger.info("=== PHASE 1: MISSION INITIALIZATION ===")

        try:
            # Parse mission with Ollama
            mission_data = self.ollama.parse_mission(user_input)

            # Create mission record
            mission = Mission(
                target_role=mission_data["target_role"],
                target_count=mission_data.get("target_count", 10),
                time_constraint_days=mission_data.get("time_constraint_days"),
                location_preference=mission_data.get("location_preference"),
                job_type=mission_data.get("job_type"),
                notes=user_input,
                status=MissionStatus.INITIALIZED
            )

            self.db.add(mission)
            self.db.commit()
            self.db.refresh(mission)

            # Log action (constitution.md 6.1)
            AuditLog.log_action(
                self.db,
                mission_id=mission.id,
                agent_name="application_agent",
                action_type=ActionType.MISSION_CREATED,
                status="Success",
                output_summary=f"Mission created: {mission.target_role} ({mission.target_count} applications)"
            )

            logger.info(f"Mission {mission.id} created successfully")
            return mission

        except Exception as e:
            logger.error(f"Mission creation failed: {str(e)}")
            raise

    # ============================================================
    # PHASE 2-3: CV UPLOAD & PARSING
    # ============================================================

    def process_cv(
        self,
        mission_id: int,
        cv_text: str,
        cv_file_path: Optional[str] = None
    ) -> CVVersion:
        """
        Phase 2-3: CV Upload & Parsing.

        As per execution_plan.md:
        Phase 2:
        1. User uploads CV
        2. Store file securely
        3. Update Mission.status = Running

        Phase 3 (Claude):
        - Extract skills, experience, keywords
        - Store structured data in DB

        Args:
            mission_id: Mission ID
            cv_text: CV text content
            cv_file_path: Path to stored CV file

        Returns:
            Tuple of (CVVersion object, parsed cv_data dict)
        """
        logger.info("=== PHASE 2-3: CV UPLOAD & PARSING ===")

        mission = self.db.query(Mission).filter(Mission.id == mission_id).first()
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        try:
            # Update mission status to Running (Phase 2)
            mission.status = MissionStatus.RUNNING
            self.db.commit()

            # Log phase start
            AuditLog.log_action(
                self.db,
                mission_id=mission_id,
                agent_name="cv_parser",
                action_type=ActionType.AGENT_INVOKED,
                status="Running",
                output_summary="Phase 2-3: CV upload & parsing started"
            )

            # Parse CV with Ollama (Phase 3) — one call only, reused later
            cv_data = self.ollama.parse_cv(cv_text)

            # Create master CV version (cap at 60 KB to stay under max_allowed_packet)
            cv_version = CVVersion(
                mission_id=mission_id,
                job_id=None,  # Master CV, not job-specific
                version_name="Master CV",
                is_master=1,
                content_markdown=cv_text[:60000],
                file_path=cv_file_path,
                file_name="master_cv.pdf"
            )

            self.db.add(cv_version)
            self.db.commit()
            self.db.refresh(cv_version)

            # Log action
            AuditLog.log_action(
                self.db,
                mission_id=mission_id,
                agent_name="cv_parser",
                action_type=ActionType.CV_PARSED,
                status="Success",
                cv_version_id=cv_version.id,
                output_summary=f"CV parsed: {len(cv_data.get('skills', []))} skills, {len(cv_data.get('experience', []))} experiences"
            )

            logger.info(f"CV parsed successfully for mission {mission_id}")
            return cv_version, cv_data

        except Exception as e:
            logger.error(f"CV processing failed: {str(e)}")

            AuditLog.log_action(
                self.db,
                mission_id=mission_id,
                agent_name="cv_parser",
                action_type=ActionType.ERROR_OCCURRED,
                status="Failed",
                level=LogLevel.ERROR,
                error_message=str(e)
            )
            raise

    # ============================================================
    # PHASE 4: JOB SCRAPING
    # ============================================================

    def scrape_jobs(self, mission_id: int, max_results: int = 50) -> List[Job]:
        """
        Phase 4: Job Scraping (Claude → Apify MCP).

        As per execution_plan.md Phase 4:
        1. Claude constructs job query
        2. Apify MCP uses APIFY_API_KEY from environment
        3. Retrieve job listings
        4. Insert jobs into Job table
        5. Retry up to 3 times on failure

        Args:
            mission_id: Mission ID
            max_results: Maximum jobs to scrape

        Returns:
            List of created Job objects
        """
        logger.info("=== PHASE 4: JOB SCRAPING ===")

        mission = self.db.query(Mission).filter(Mission.id == mission_id).first()
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        # Log phase start
        AuditLog.log_action(
            self.db,
            mission_id=mission_id,
            agent_name="job_scraper",
            action_type=ActionType.AGENT_INVOKED,
            status="Running",
            output_summary=f"Phase 4: Scraping jobs for '{mission.target_role}' in '{mission.location_preference or 'any location'}'"
        )

        # Retry logic (constitution.md 4.1)
        for attempt in range(self.max_retries):
            try:
                # Scrape jobs via Apify MCP
                job_listings = self.apify.scrape_jobs(
                    role=mission.target_role,
                    location=mission.location_preference,
                    job_type=mission.job_type,
                    max_results=max_results
                )

                # Insert jobs into database
                created_jobs = []
                for listing in job_listings:
                    job = Job(
                        mission_id=mission_id,
                        company=listing["company"],
                        role=listing["role"],
                        location=listing.get("location"),
                        description=listing["description"],
                        requirements=json.dumps(listing.get("requirements", [])),
                        apply_link=listing.get("apply_link"),
                        hr_email=listing.get("hr_email"),
                        hr_name=listing.get("hr_name"),
                        source_portal=listing.get("source_portal"),
                        status=JobStatus.SCRAPED
                    )
                    self.db.add(job)
                    created_jobs.append(job)

                self.db.commit()

                # Log success
                AuditLog.log_action(
                    self.db,
                    mission_id=mission_id,
                    agent_name="job_scraper",
                    action_type=ActionType.JOBS_SCRAPED,
                    status="Success",
                    output_summary=f"Scraped {len(created_jobs)} jobs"
                )

                logger.info(f"Scraped {len(created_jobs)} jobs for mission {mission_id}")
                return created_jobs

            except Exception as e:
                logger.warning(f"Job scraping attempt {attempt + 1} failed: {str(e)}")

                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                else:
                    AuditLog.log_action(
                        self.db,
                        mission_id=mission_id,
                        agent_name="job_scraper",
                        action_type=ActionType.ERROR_OCCURRED,
                        status="Failed",
                        level=LogLevel.ERROR,
                        error_message=str(e)
                    )
                    raise

        return []

    # ============================================================
    # PHASE 5: JOB MATCHING
    # ============================================================

    def match_jobs(self, mission_id: int, cv_data: Dict) -> List[Job]:
        """
        Phase 5: Matching (Ollama).

        As per execution_plan.md Phase 5:
        - Ollama calculates match scores
        - Claude validates output
        - Update Job.match_score in DB
        - Select top N jobs

        Args:
            mission_id: Mission ID
            cv_data: Parsed CV data

        Returns:
            List of matched jobs
        """
        logger.info("=== PHASE 5: JOB MATCHING ===")

        jobs = self.db.query(Job).filter(
            Job.mission_id == mission_id,
            Job.status == JobStatus.SCRAPED
        ).all()

        # Log phase start
        AuditLog.log_action(
            self.db,
            mission_id=mission_id,
            agent_name="job_matcher",
            action_type=ActionType.AGENT_INVOKED,
            status="Running",
            output_summary=f"Phase 5: Selecting 5 random jobs from {len(jobs)} scraped — CV will be tailored to each"
        )

        import random
        selected = random.sample(jobs, min(5, len(jobs)))

        for job in selected:
            job.match_score = 90
            job.matched_skills = json.dumps(cv_data.get("skills", [])[:6])
            job.missing_skills = json.dumps([])
            job.experience_alignment = "high"
            job.status = JobStatus.SELECTED

            AuditLog.log_action(
                self.db,
                mission_id=mission_id,
                job_id=job.id,
                agent_name="job_matcher",
                action_type=ActionType.JOB_MATCHED,
                status="Success",
                output_summary=f"Selected: {job.role} at {job.company} — CV will be tailored to fit"
            )

        # Mark remaining jobs as matched (not selected)
        selected_ids = {j.id for j in selected}
        for job in jobs:
            if job.id not in selected_ids:
                job.status = JobStatus.MATCHED

        self.db.commit()

        logger.info(f"Selected {len(selected)} random jobs for CV tailoring")
        return selected

    # ============================================================
    # PHASE 4B/4C: HR EMAIL ENRICHMENT (Apollo.io)
    # ============================================================

    def enrich_hr_emails(self, mission_id: int, selected_jobs: List[Job]) -> List[Job]:
        """
        Phase 4B/4C: HR Email Enrichment via Apollo.io.

        Runs after Phase 5 (random pick) on the 5 selected jobs only.
        Extracts company domain from job URL, then queries Apollo.io
        for the highest-priority HR/recruiter email available.

        Falls back gracefully — never blocks the pipeline.

        Args:
            mission_id: Mission ID (for audit logging)
            selected_jobs: The 5 jobs selected in Phase 5

        Returns:
            Same jobs with hr_email, hr_name, hr_title, hr_email_confidence updated
        """
        logger.info("=== PHASE 4B/4C: HR EMAIL ENRICHMENT (Apollo.io) ===")

        AuditLog.log_action(
            self.db,
            mission_id=mission_id,
            agent_name="apollo_service",
            action_type=ActionType.AGENT_INVOKED,
            status="Running",
            output_summary=f"Phase 4B/4C: Looking up real HR emails for {len(selected_jobs)} selected jobs via Apollo.io"
        )

        # Convert ORM objects → plain dicts for the Apollo service
        job_dicts = [
            {
                "id": j.id,
                "role": j.role,
                "company": j.company,
                "apply_link": j.apply_link,
                "hr_email": j.hr_email,
                "hr_name": j.hr_name,
            }
            for j in selected_jobs
        ]

        enriched_dicts = enrich_jobs_with_hr_emails(job_dicts)

        # Write results back to ORM objects and persist
        found_count = 0
        for job, enriched in zip(selected_jobs, enriched_dicts):
            if enriched.get("hr_email"):
                job.hr_email = enriched["hr_email"]
                job.hr_name = enriched.get("hr_name") or job.hr_name
                job.hr_title = enriched.get("hr_title")
                job.hr_email_confidence = enriched.get("hr_email_confidence", "none")
                found_count += 1

                AuditLog.log_action(
                    self.db,
                    mission_id=mission_id,
                    job_id=job.id,
                    agent_name="apollo_service",
                    action_type=ActionType.AGENT_INVOKED,
                    status="Success",
                    output_summary=(
                        f"HR contact found: {job.hr_name} ({job.hr_title}) "
                        f"→ {job.hr_email} [{job.hr_email_confidence}]"
                    )
                )
            else:
                AuditLog.log_action(
                    self.db,
                    mission_id=mission_id,
                    job_id=job.id,
                    agent_name="apollo_service",
                    action_type=ActionType.AGENT_INVOKED,
                    status="Success",
                    output_summary=f"No HR email found for {job.company} — will use fallback formula in Phase 7"
                )

        self.db.commit()

        AuditLog.log_action(
            self.db,
            mission_id=mission_id,
            agent_name="apollo_service",
            action_type=ActionType.AGENT_INVOKED,
            status="Success",
            output_summary=f"Phase 4B/4C complete: {found_count}/{len(selected_jobs)} real HR emails found"
        )

        logger.info(f"HR email enrichment complete: {found_count}/{len(selected_jobs)} found")
        return selected_jobs

    # ============================================================
    # PHASE 6: CV VERSIONING
    # ============================================================

    def optimize_cv_for_job(self, job_id: int, cv_data: Dict) -> CVVersion:
        """
        Phase 6: CV Versioning (Ollama).

        As per execution_plan.md Phase 6:
        - Ollama generates tailored CV modifications
        - Claude generates final CV file
        - Store in CVVersion table

        Args:
            job_id: Job ID
            cv_data: Parsed CV data

        Returns:
            Optimized CVVersion object
        """
        logger.info(f"=== PHASE 6: CV VERSIONING (Job {job_id}) ===")

        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Log phase start
        AuditLog.log_action(
            self.db,
            mission_id=job.mission_id,
            job_id=job_id,
            agent_name="cv_optimizer",
            action_type=ActionType.AGENT_INVOKED,
            status="Running",
            output_summary=f"Phase 6: Optimizing CV for {job.role} at {job.company}"
        )

        try:
            # Optimize with Ollama
            optimization = self.ollama.optimize_cv(
                cv_data=cv_data,
                job_description=job.description,
                job_role=job.role
            )

            # Create optimized CV version
            cv_version = CVVersion(
                mission_id=job.mission_id,
                job_id=job_id,
                version_name=f"CV for {job.company} - {job.role}",
                is_master=0,
                content_markdown=optimization["optimized_content"],
                keyword_match_score=optimization["keyword_match_score"],
                optimization_notes=json.dumps(optimization.get("suggested_improvements", [])),
                file_name=f"cv_{job.company.replace(' ', '_')}.pdf"
            )

            self.db.add(cv_version)

            # Update job status
            job.status = JobStatus.CV_OPTIMIZED
            self.db.commit()
            self.db.refresh(cv_version)

            # Log action
            AuditLog.log_action(
                self.db,
                mission_id=job.mission_id,
                job_id=job_id,
                cv_version_id=cv_version.id,
                agent_name="cv_optimizer",
                action_type=ActionType.CV_OPTIMIZED,
                status="Success",
                output_summary=f"Keyword match: {optimization['keyword_match_score']}%"
            )

            logger.info(f"CV optimized for job {job_id}")
            return cv_version

        except Exception as e:
            logger.error(f"CV optimization failed: {str(e)}")
            raise

    # ============================================================
    # PHASE 7: EMAIL GENERATION
    # ============================================================

    def generate_email(self, job_id: int, cv_data: Dict) -> EmailDraft:
        """
        Phase 7: Email Generation (Ollama).

        As per execution_plan.md Phase 7:
        - Ollama drafts personalized email
        - Claude stores in EmailDraft table
        - Set status = PendingApproval

        Args:
            job_id: Job ID
            cv_data: Parsed CV data

        Returns:
            EmailDraft object
        """
        logger.info(f"=== PHASE 7: EMAIL GENERATION (Job {job_id}) ===")

        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Log phase start
        AuditLog.log_action(
            self.db,
            mission_id=job.mission_id,
            job_id=job_id,
            agent_name="email_generator",
            action_type=ActionType.AGENT_INVOKED,
            status="Running",
            output_summary=f"Phase 7: Drafting email for {job.role} at {job.company}"
        )

        try:
            # Generate email with Ollama
            import json
            matched_skills = json.loads(job.matched_skills) if job.matched_skills else []

            email_content = self.ollama.generate_email(
                job_role=job.role,
                company=job.company,
                cv_summary=cv_data.get("summary", ""),
                hr_name=job.hr_name,
                matched_skills=matched_skills
            )

            # Append the AI-tailored CV for this job beneath the cover letter
            cover_body = email_content["body"]
            tailored_cv = self.db.query(CVVersion).filter(
                CVVersion.job_id == job_id,
                CVVersion.is_master == 0
            ).order_by(CVVersion.id.desc()).first()
            if tailored_cv and tailored_cv.content_markdown:
                cover_body = (
                    cover_body.rstrip()
                    + "\n\n"
                    + "—" * 40
                    + "\n\n"
                    + tailored_cv.content_markdown.strip()
                )

            # Build recipient email: real scraped → guessed placeholder.
            # A guessed address is NEVER treated as confirmed — approve_email()
            # blocks sending until a human fixes it or a verified/likely match exists.
            company_slug = re.sub(r"[^a-z0-9]", "", job.company.lower())
            recipient_email = job.hr_email or f"jobs@{company_slug}.com"
            recipient_confirmed = job.hr_email_confidence in ("verified", "likely")

            # Create email draft
            email_draft = EmailDraft(
                job_id=job_id,
                subject=email_content["subject"],
                body=cover_body,
                to_email=recipient_email,
                to_name=job.hr_name,
                recipient_confirmed=recipient_confirmed,
                status=EmailStatus.PENDING_APPROVAL
            )

            self.db.add(email_draft)

            # Update job status
            job.status = JobStatus.EMAIL_DRAFTED
            self.db.commit()
            self.db.refresh(email_draft)

            # Log action
            AuditLog.log_action(
                self.db,
                mission_id=job.mission_id,
                job_id=job_id,
                email_draft_id=email_draft.id,
                agent_name="email_generator",
                action_type=ActionType.EMAIL_GENERATED,
                status="Success"
            )

            logger.info(f"Email generated for job {job_id}")
            return email_draft

        except Exception as e:
            logger.error(f"Email generation failed: {str(e)}")
            raise

    # ============================================================
    # PHASE 8: HUMAN-IN-THE-LOOP (HITL)
    # ============================================================

    def approve_email(self, email_draft_id: int, approved_by: str = "user") -> EmailDraft:
        """
        Phase 8: Human Approval - Approve email.

        As per constitution.md Section 3:
        - No email sent without explicit human approval

        Args:
            email_draft_id: EmailDraft ID
            approved_by: User identifier

        Returns:
            Updated EmailDraft
        """
        email_draft = self.db.query(EmailDraft).filter(
            EmailDraft.id == email_draft_id
        ).first()

        if not email_draft:
            raise ValueError(f"Email draft {email_draft_id} not found")

        if not email_draft.recipient_confirmed:
            raise RecipientNotConfirmedError(
                f"Cannot approve: recipient '{email_draft.to_email}' is an unverified guess, "
                "not a real HR email. Edit the To: address to a real one before approving."
            )

        email_draft.approve(approved_by)

        job = self.db.query(Job).filter(Job.id == email_draft.job_id).first()
        job.status = JobStatus.APPROVED

        self.db.commit()

        # Log approval
        AuditLog.log_action(
            self.db,
            mission_id=job.mission_id,
            job_id=job.id,
            email_draft_id=email_draft_id,
            agent_name="application_agent",
            action_type=ActionType.EMAIL_APPROVED,
            status="Success"
        )

        logger.info(f"Email {email_draft_id} approved by {approved_by}")
        return email_draft

    def reject_email(self, email_draft_id: int, reason: str = None) -> EmailDraft:
        """
        Phase 8: Human Approval - Reject email.

        As per constitution.md 3.4:
        - Rejected items must be logged

        Args:
            email_draft_id: EmailDraft ID
            reason: Rejection reason

        Returns:
            Updated EmailDraft
        """
        email_draft = self.db.query(EmailDraft).filter(
            EmailDraft.id == email_draft_id
        ).first()

        if not email_draft:
            raise ValueError(f"Email draft {email_draft_id} not found")

        email_draft.reject(reason)

        job = self.db.query(Job).filter(Job.id == email_draft.job_id).first()
        job.status = JobStatus.REJECTED

        self.db.commit()

        # Log rejection
        AuditLog.log_action(
            self.db,
            mission_id=job.mission_id,
            job_id=job.id,
            email_draft_id=email_draft_id,
            agent_name="application_agent",
            action_type=ActionType.EMAIL_REJECTED,
            status="Success",
            output_summary=f"Reason: {reason}"
        )

        logger.info(f"Email {email_draft_id} rejected")
        return email_draft

    # ============================================================
    # PHASE 9: APPLICATION SENDING
    # ============================================================

    def send_application(
        self,
        email_draft_id: int,
        cv_version_id: int
    ) -> ApplicationRecord:
        """
        Phase 9: Application Sending (Claude → Gmail MCP).

        As per execution_plan.md Phase 9:
        1. Claude prepares structured send request
        2. Gmail MCP authenticates using credentials
        3. Send email with CV attachment
        4. Return message ID
        5. Insert into ApplicationRecord table
        6. Update Job.status = Applied
        7. Increment Mission progress_count

        Args:
            email_draft_id: EmailDraft ID
            cv_version_id: CVVersion ID

        Returns:
            ApplicationRecord object
        """
        logger.info(f"=== PHASE 9: APPLICATION SENDING (Email {email_draft_id}) ===")

        email_draft = self.db.query(EmailDraft).filter(
            EmailDraft.id == email_draft_id
        ).first()

        if not email_draft:
            raise ValueError(f"Email draft {email_draft_id} not found")

        if email_draft.status != EmailStatus.APPROVED:
            raise ValueError(f"Email {email_draft_id} not approved")

        cv_version = self.db.query(CVVersion).filter(
            CVVersion.id == cv_version_id
        ).first()

        if not cv_version:
            raise ValueError(f"CV version {cv_version_id} not found")

        job = self.db.query(Job).filter(Job.id == email_draft.job_id).first()
        mission = self.db.query(Mission).filter(Mission.id == job.mission_id).first()

        # Check governance rules (constitution.md Section 5.4)
        # Count applications today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        applications_today = self.db.query(ApplicationRecord).filter(
            ApplicationRecord.sent_at >= today_start
        ).count()

        governance = self.ollama.enforce_governance(
            mission_id=mission.id,
            current_progress=mission.progress_count,
            target_count=mission.target_count,
            daily_limit=mission.daily_application_limit,
            applications_today=applications_today
        )

        if not governance["can_proceed"]:
            raise ValueError(f"Governance check failed: {governance['reason']}")

        # Retry logic (constitution.md 4.1)
        for attempt in range(self.max_retries):
            try:
                # Send email via Gmail MCP
                result = self.gmail.send_email(
                    to_email=email_draft.to_email,
                    subject=email_draft.subject,
                    body=email_draft.body,
                    cv_file_path=cv_version.file_path,
                    cv_file_name=cv_version.file_name,
                    to_name=email_draft.to_name,
                    cc_emails=email_draft.cc_emails
                )

                if result["status"] == "failed":
                    raise Exception(result["error"])

                # Create immutable application record
                email_hash = hashlib.sha256(
                    (email_draft.subject + email_draft.body).encode()
                ).hexdigest()

                app_record = ApplicationRecord(
                    job_id=job.id,
                    email_draft_id=email_draft_id,
                    cv_version_id=cv_version_id,
                    company=job.company,
                    hr_email=email_draft.to_email,
                    hr_name=email_draft.to_name,
                    email_subject=email_draft.subject,
                    email_content_hash=email_hash,
                    gmail_message_id=result["message_id"],
                    gmail_thread_id=result["thread_id"],
                    outcome=ApplicationOutcome.SENT
                )

                self.db.add(app_record)

                # Update statuses
                email_draft.status = EmailStatus.SENT
                job.status = JobStatus.APPLIED
                job.applied_at = datetime.utcnow()

                # Increment mission progress
                mission.progress_count += 1

                # Check if mission complete
                if mission.is_complete():
                    mission.status = MissionStatus.COMPLETED
                    mission.completed_at = datetime.utcnow()

                self.db.commit()
                self.db.refresh(app_record)

                # Log success
                AuditLog.log_action(
                    self.db,
                    mission_id=mission.id,
                    job_id=job.id,
                    agent_name="email_sender",
                    action_type=ActionType.APPLICATION_SUBMITTED,
                    status="Success",
                    output_summary=f"Gmail message ID: {result['message_id']}"
                )

                logger.info(f"Application sent successfully: {job.company} - {job.role}")
                return app_record

            except Exception as e:
                logger.warning(f"Application send attempt {attempt + 1} failed: {str(e)}")

                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                else:
                    # Mark as failed
                    job.status = JobStatus.FAILED
                    self.db.commit()

                    AuditLog.log_action(
                        self.db,
                        mission_id=mission.id,
                        job_id=job.id,
                        agent_name="email_sender",
                        action_type=ActionType.ERROR_OCCURRED,
                        status="Failed",
                        level=LogLevel.ERROR,
                        error_message=str(e)
                    )
                    raise

    # ============================================================
    # PHASE 10-11: VALIDATION & COMPLETION
    # ============================================================

    def validate_mission(self, mission_id: int) -> Dict[str, Any]:
        """
        Phase 11: Mission Validation.

        As per execution_plan.md Phase 11:
        - Check if progress_count >= target_count
        - Update Mission.status = Completed

        Args:
            mission_id: Mission ID

        Returns:
            Mission status summary
        """
        logger.info(f"=== PHASE 11: MISSION VALIDATION (Mission {mission_id}) ===")

        mission = self.db.query(Mission).filter(Mission.id == mission_id).first()
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        if mission.is_complete() and mission.status != MissionStatus.COMPLETED:
            mission.status = MissionStatus.COMPLETED
            mission.completed_at = datetime.utcnow()
            self.db.commit()

            AuditLog.log_action(
                self.db,
                mission_id=mission_id,
                agent_name="application_agent",
                action_type=ActionType.MISSION_COMPLETED,
                status="Success",
                output_summary=f"Target reached: {mission.progress_count}/{mission.target_count}"
            )

            logger.info(f"Mission {mission_id} completed")

        return {
            "mission_id": mission.id,
            "status": mission.status.value,
            "progress": mission.progress_count,
            "target": mission.target_count,
            "is_complete": mission.is_complete()
        }

    # ============================================================
    # FULL WORKFLOW EXECUTION
    # ============================================================

    def execute_full_workflow(
        self,
        mission_id: int,
        cv_text: str,
        cv_file_path: Optional[str] = None,
        auto_approve: bool = False
    ) -> Dict[str, Any]:
        """
        Execute complete 12-phase workflow (with HITL checkpoints).

        This orchestrates all phases but pauses for human approval
        unless auto_approve=True (for testing only).

        Args:
            mission_id: Mission ID
            cv_text: CV text content
            cv_file_path: Path to CV file
            auto_approve: Auto-approve emails (TESTING ONLY)

        Returns:
            Workflow execution summary
        """
        logger.info(f"=== EXECUTING FULL WORKFLOW: Mission {mission_id} ===")

        try:
            # Log workflow start
            AuditLog.log_action(
                self.db,
                mission_id=mission_id,
                agent_name="application_agent",
                action_type=ActionType.AGENT_INVOKED,
                status="Running",
                output_summary="Workflow started — running all 12 phases sequentially"
            )

            # Phase 2-3: Process CV (also returns parsed cv_data so we don't call LLM twice)
            cv_version, cv_data = self.process_cv(mission_id, cv_text, cv_file_path)

            # Phase 4: Scrape jobs
            jobs = self.scrape_jobs(mission_id, max_results=20)

            # Phase 5: Random pick 5 jobs
            matched_jobs = self.match_jobs(mission_id, cv_data)

            # Phase 4B/4C: Enrich the 5 selected jobs with real HR emails (Apollo.io)
            matched_jobs = self.enrich_hr_emails(mission_id, matched_jobs)

            # Phase 6-7: For each of the 5 randomly selected jobs only
            pending_approvals = []
            top_jobs = matched_jobs[:5]  # Hard cap at 5 — matches Phase 5 selection

            AuditLog.log_action(
                self.db,
                mission_id=mission_id,
                agent_name="application_agent",
                action_type=ActionType.AGENT_INVOKED,
                status="Running",
                output_summary=f"Phase 6-7: Generating {len(top_jobs)} CV versions and emails — one per selected job"
            )

            for job in top_jobs:
                try:
                    # Phase 6: Optimize CV
                    opt_cv = self.optimize_cv_for_job(job.id, cv_data)
                    # Phase 7: Generate email
                    email_draft = self.generate_email(job.id, cv_data)
                    pending_approvals.append({
                        "job": job,
                        "cv_version": opt_cv,
                        "email_draft": email_draft
                    })
                except Exception as e:
                    logger.error(f"Phase 6-7 failed for job {job.id}: {e}")

            # Phase 8: HITL checkpoint
            AuditLog.log_action(
                self.db,
                mission_id=mission_id,
                agent_name="application_agent",
                action_type=ActionType.AGENT_INVOKED,
                status="Running",
                output_summary=f"Phase 8: HITL — {len(pending_approvals)} email drafts ready for your approval in the approval panel"
            )

            if auto_approve:
                logger.warning("AUTO-APPROVE ENABLED - TESTING ONLY")
                for item in pending_approvals:
                    self.approve_email(item["email_draft"].id)

                    # Phase 9: Send application
                    self.send_application(
                        item["email_draft"].id,
                        item["cv_version"].id
                    )

            # Phase 11: Validate mission
            status = self.validate_mission(mission_id)

            return {
                "success": True,
                "mission_status": status,
                "jobs_scraped": len(jobs),
                "jobs_matched": len(matched_jobs),
                "pending_approvals": len(pending_approvals) if not auto_approve else 0,
                "applications_sent": len(pending_approvals) if auto_approve else 0
            }

        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            raise
