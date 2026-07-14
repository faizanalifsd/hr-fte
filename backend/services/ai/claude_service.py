"""
Claude Service - Master Orchestrator.

As per execution_plan.md:
- Mission parsing
- Planning & orchestration
- Tool invocation (MCP calls)
- Governance enforcement
- HITL validation
- Final decision making
"""

import os
import logging
from typing import Dict, List, Optional, Any
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class ClaudeService:
    """
    Claude AI service for orchestration and high-level decision making.

    Model: Claude Sonnet (default) or Opus for complex decisions
    """

    def __init__(self):
        """Initialize Claude service with API key."""
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found in environment variables. "
                "Please set it before running the application."
            )

        self.client = Anthropic(api_key=self.api_key)
        self.default_model = "claude-sonnet-4-5-20250929"
        self.max_tokens = 4096

    def parse_mission(self, user_input: str) -> Dict[str, Any]:
        """
        Parse mission from user input (Phase 1).

        Args:
            user_input: User's mission description

        Returns:
            {
                "target_role": str,
                "target_count": int,
                "time_constraint_days": Optional[int],
                "location_preference": Optional[str],
                "job_type": Optional[str],
                "additional_notes": Optional[str]
            }
        """
        logger.info("Parsing mission from user input")

        prompt = f"""
You are a mission parser for a job application system.

Parse the following user input into structured mission data:

User Input: "{user_input}"

Extract:
1. Target role (required)
2. Target application count (required, default to 10 if not specified)
3. Time constraint in days (optional)
4. Location preference (optional)
5. Job type preference (optional, e.g., Full-time, Contract, Remote)

Return ONLY a JSON object with these fields. No explanation.

Example:
{{
    "target_role": "Python Developer",
    "target_count": 20,
    "time_constraint_days": 7,
    "location_preference": "Remote",
    "job_type": "Full-time"
}}
"""

        try:
            response = self.client.messages.create(
                model=self.default_model,
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            result_text = response.content[0].text.strip()

            # Parse JSON response
            import json
            mission_data = json.loads(result_text)

            logger.info(f"Mission parsed: {mission_data}")
            return mission_data

        except Exception as e:
            logger.error(f"Mission parsing failed: {str(e)}")
            raise

    def validate_threshold_logic(
        self,
        match_score: float,
        matched_skills: List[str],
        missing_skills: List[str]
    ) -> Dict[str, Any]:
        """
        Validate job matching threshold and make application decision.

        As per execution_plan.md Phase 5:
        - Claude validates threshold logic
        - Approves or blocks downstream workflow

        Args:
            match_score: Match score from Gemini (0-100)
            matched_skills: Skills that match
            missing_skills: Skills that are missing

        Returns:
            {
                "decision": "Apply" | "Optimize First" | "Skip",
                "approved": bool,
                "reasoning": str
            }
        """
        if match_score >= 80:
            decision = "Apply"
            approved = True
            reasoning = "Strong match - proceed with application"
        elif match_score >= 60:
            decision = "Optimize First"
            approved = True
            reasoning = "Good match - optimize CV before applying"
        else:
            decision = "Skip"
            approved = False
            reasoning = "Insufficient match - skip this opportunity"

        return {
            "decision": decision,
            "approved": approved,
            "reasoning": reasoning
        }

    def enforce_governance(
        self,
        mission_id: int,
        current_progress: int,
        target_count: int,
        daily_limit: int,
        applications_today: int
    ) -> Dict[str, Any]:
        """
        Enforce governance rules from constitution.md.

        Rules:
        - Rate limiting (max applications per day)
        - Mission completion tracking
        - Security compliance

        Returns:
            {
                "can_proceed": bool,
                "reason": str,
                "remaining_quota": int
            }
        """
        # Check if mission is already complete
        if current_progress >= target_count:
            return {
                "can_proceed": False,
                "reason": "Mission target already reached",
                "remaining_quota": 0
            }

        # Check daily rate limit (constitution.md 5.4)
        if applications_today >= daily_limit:
            return {
                "can_proceed": False,
                "reason": f"Daily application limit reached ({daily_limit})",
                "remaining_quota": 0
            }

        remaining_quota = min(
            target_count - current_progress,
            daily_limit - applications_today
        )

        return {
            "can_proceed": True,
            "reason": "Governance check passed",
            "remaining_quota": remaining_quota
        }

    def validate_email_content(
        self,
        email_subject: str,
        email_body: str,
        job_role: str,
        company: str
    ) -> Dict[str, Any]:
        """
        Validate generated email content before HITL approval.

        Checks:
        - Appropriate tone
        - No spam behavior
        - Personalization
        - Professionalism

        Returns:
            {
                "is_valid": bool,
                "issues": List[str],
                "suggestions": List[str]
            }
        """
        prompt = f"""
You are validating a job application email for quality and professionalism.

Company: {company}
Role: {job_role}

Subject: {email_subject}

Body:
{email_body}

Check for:
1. Professional tone
2. Personalization (not generic spam)
3. Appropriate length (< 250 words)
4. No exaggerated claims
5. Proper grammar

Return JSON:
{{
    "is_valid": true/false,
    "issues": ["issue1", "issue2"],
    "suggestions": ["suggestion1", "suggestion2"]
}}
"""

        try:
            response = self.client.messages.create(
                model=self.default_model,
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            result_text = response.content[0].text.strip()

            import json
            validation = json.loads(result_text)

            return validation

        except Exception as e:
            logger.error(f"Email validation failed: {str(e)}")
            # Default to valid if validation fails
            return {
                "is_valid": True,
                "issues": [],
                "suggestions": []
            }

    def make_final_decision(
        self,
        context: str,
        question: str,
        options: List[str]
    ) -> str:
        """
        Make final decision for complex scenarios.

        Used when automated logic is insufficient and
        AI judgment is needed.

        Args:
            context: Situation context
            question: Decision question
            options: Available options

        Returns:
            Selected option with reasoning
        """
        prompt = f"""
Context: {context}

Question: {question}

Options:
{chr(10).join(f"{i+1}. {opt}" for i, opt in enumerate(options))}

Make a decision and explain your reasoning briefly.
Return format: "Option X: reasoning"
"""

        try:
            response = self.client.messages.create(
                model=self.default_model,
                max_tokens=512,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            decision = response.content[0].text.strip()
            logger.info(f"Decision made: {decision}")
            return decision

        except Exception as e:
            logger.error(f"Decision making failed: {str(e)}")
            # Default to first option
            return f"Option 1: {options[0]} (default fallback)"
