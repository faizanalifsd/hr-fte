"""
LLM Service — OpenRouter (primary) + Groq (fallback) + Rule-based (final fallback).

Provider cascade:
  1. OpenRouter     — 200+ models (meta-llama/llama-3.1-8b-instruct:free)
  2. Groq           — ultra-fast inference (llama-3.3-70b-versatile)
  3. Rule-based     — deterministic logic, no API required

All methods return the same schema regardless of which provider handled the call,
so the orchestrator is fully decoupled from provider internals.
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider constants
# ---------------------------------------------------------------------------

GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = "llama-3.3-70b-versatile"

OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"


def _get_openai_client(base_url: str, api_key: str):
    """Return an openai.OpenAI client with timeout + no retries to prevent background thread hangs."""
    from openai import OpenAI  # lazy import — avoids hard dependency at import time
    import httpx
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=httpx.Timeout(30.0, connect=10.0),  # 30s total, 10s connect
        max_retries=0,   # disable SDK-level retries — we handle fallback ourselves
    )


def _call_llm(prompt: str, system: str = "You are a helpful AI assistant.", max_tokens: int = 1024) -> Optional[str]:
    """
    Try Groq (primary) then OpenRouter (fallback), then return None (rule-based).
    Groq is primary because OpenRouter free tier is frequently rate-limited.
    """
    groq_key = os.getenv("GROQ_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    # --- Groq (primary — fast, reliable free tier) ---
    if groq_key:
        try:
            client = _get_openai_client(GROQ_BASE_URL, groq_key)
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=max_tokens,
            )
            text = response.choices[0].message.content.strip()
            logger.info(f"LLM: Groq responded ({len(text)} chars)")
            return text
        except Exception as exc:
            logger.warning(f"LLM: Groq failed — {exc}")

    # --- OpenRouter (fallback) ---
    if openrouter_key:
        try:
            client = _get_openai_client(OPENROUTER_BASE_URL, openrouter_key)
            response = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=max_tokens,
            )
            text = response.choices[0].message.content.strip()
            logger.info(f"LLM: OpenRouter responded ({len(text)} chars)")
            return text
        except Exception as exc:
            logger.warning(f"LLM: OpenRouter failed — {exc}")

    logger.warning("LLM: All providers failed — using rule-based fallback")
    return None


def _parse_json_from_llm(text: str) -> Optional[Dict]:
    """Extract the first JSON object from an LLM response string."""
    try:
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
        # Find the first {...} block
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


# ---------------------------------------------------------------------------
# Main service class
# ---------------------------------------------------------------------------

class LLMService:
    """
    Unified AI sub-agent service.

    Cascades: Groq → OpenRouter → rule-based fallback.
    The orchestrator only calls this class — never imports openai directly.
    """

    def __init__(self):
        or_configured = bool(os.getenv("OPENROUTER_API_KEY"))
        groq_configured = bool(os.getenv("GROQ_API_KEY"))
        if or_configured:
            logger.info("LLMService: OpenRouter primary configured")
        if groq_configured:
            logger.info("LLMService: Groq fallback configured")
        if not or_configured and not groq_configured:
            logger.warning("LLMService: No LLM API keys — rule-based mode only")

    # ------------------------------------------------------------------ #
    # Public interface                                                     #
    # ------------------------------------------------------------------ #

    def parse_mission(self, user_input: str) -> Dict[str, Any]:
        """Parse a natural-language mission request into structured fields."""
        prompt = f"""Parse the following job search mission request and return a JSON object with these exact fields:
- target_role (string): the job title or role being searched for
- target_count (integer): number of jobs to apply for (1-50)
- time_constraint_days (integer or null): deadline in days, null if not specified
- location_preference (string or null): city/country/remote preference, null if not specified
- job_type (string): one of "Full-time", "Part-time", "Contract", "Remote"

Mission request: "{user_input}"

Respond with ONLY a JSON object, no explanation."""

        text = _call_llm(prompt)
        if text:
            data = _parse_json_from_llm(text)
            if data and "target_role" in data and "target_count" in data:
                data["target_count"] = max(1, min(int(data.get("target_count", 10)), 50))
                logger.info(f"parse_mission: LLM parsed → {data['target_role']}")
                return data

        logger.info("parse_mission: using rule-based fallback")
        return self._fallback_parse_mission(user_input)

    def parse_cv(self, cv_text: str) -> Dict[str, Any]:
        """Parse CV text into structured data."""
        prompt = f"""Extract structured information from this CV/resume text and return a JSON object with:
- summary (string): one-sentence professional summary
- skills (array of strings): technical and professional skills
- experience (array of objects with role, company, duration, description)
- education (array of objects with degree, institution, year)
- projects (array of objects with name, description, technologies)

CV text:
{cv_text[:3000]}

Respond with ONLY a JSON object."""

        text = _call_llm(prompt)
        if text:
            data = _parse_json_from_llm(text)
            if data and "skills" in data:
                logger.info(f"parse_cv: LLM extracted {len(data.get('skills', []))} skills")
                return data

        logger.info("parse_cv: using rule-based fallback")
        return self._fallback_parse_cv(cv_text)

    def optimize_cv(
        self,
        cv_data: Dict,
        job_description: str,
        job_role: str,
    ) -> Dict[str, Any]:
        """Optimize CV content for a specific job, applying resume_editor rules."""
        skills_str = ", ".join(cv_data.get("skills", [])[:20])
        summary = cv_data.get("summary", "")

        # Serialise experience / education / projects for the prompt
        experience_lines = []
        for exp in cv_data.get("experience", [])[:5]:
            role = exp.get("role", "")
            company = exp.get("company", "")
            duration = exp.get("duration", "")
            desc = exp.get("description", "")
            experience_lines.append(f"- {role} at {company} ({duration}): {desc}")
        experience_str = "\n".join(experience_lines) or "Not provided"

        education_lines = []
        for edu in cv_data.get("education", [])[:3]:
            if isinstance(edu, dict):
                education_lines.append(
                    f"- {edu.get('degree','')} from {edu.get('institution','')} ({edu.get('year','')})"
                )
            else:
                education_lines.append(f"- {edu}")
        education_str = "\n".join(education_lines) or "Not provided"

        projects_lines = []
        for proj in cv_data.get("projects", [])[:4]:
            if isinstance(proj, dict):
                projects_lines.append(f"- {proj.get('name','')}: {proj.get('description','')}")
            else:
                projects_lines.append(f"- {proj}")
        projects_str = "\n".join(projects_lines) or ""

        prompt = f"""You are a professional resume writer. Rewrite the candidate's CV perfectly tailored for the target job. It must read like a human wrote it — a recruiter must not detect AI authorship.

=== TAILORING RULES ===
1. Mirror the job description's exact keywords, tools, and terminology throughout
2. Rewrite every experience bullet using the job's language — past roles must sound directly relevant
3. Reorder Skills so the most job-relevant skills appear first
4. Rewrite the Summary as a natural, conversational pitch mentioning the job title organically
5. Never invent metrics, titles, or experiences — only reframe what already exists

=== ANTI-AI RULES ===
NEVER use: "Leverage/Spearheaded/Utilize/Additionally/Furthermore/Results-driven/Proven track record/Passionate about/Dedicated to"
ALWAYS: Mix bullet lengths, vary openers, use rough numbers (~30%, 3-person team), no superlatives

=== OUTPUT FORMAT (CRITICAL — follow exactly) ===
Line 1: SCORE:<integer 0-100>
Line 2: IMPROVEMENTS:<improvement1>|<improvement2>|<improvement3>
Line 3: (blank)
Lines 4+: The complete tailored CV in Markdown with sections: ## Summary, ## Skills, ## Experience, ## Education (and ## Projects if applicable)

Each Experience entry:
**[Role] — [Company] ([Duration])**
- bullet
- bullet

=== INPUT ===
Job Role: {job_role}
Job Description: {job_description[:1200]}

Candidate:
Summary: {summary}
Skills: {skills_str}
Experience:
{experience_str}
Education:
{education_str}
{f"Projects:{chr(10)}{projects_str}" if projects_str else ""}"""

        text = _call_llm(prompt, max_tokens=4096)
        if text:
            lines = text.strip().splitlines()
            score = None
            improvements = []
            cv_start = 0
            for i, line in enumerate(lines):
                if line.startswith("SCORE:"):
                    try:
                        score = int(re.search(r"\d+", line).group())
                    except Exception:
                        pass
                elif line.startswith("IMPROVEMENTS:"):
                    improvements = [s.strip() for s in line[len("IMPROVEMENTS:"):].split("|") if s.strip()]
                elif line.startswith("## "):
                    cv_start = i
                    break
            optimized_content = "\n".join(lines[cv_start:]).strip() if cv_start else ""
            if score is not None and optimized_content:
                logger.info(f"optimize_cv: LLM optimized full CV for {job_role} (score={score})")
                return {
                    "keyword_match_score": score,
                    "suggested_improvements": improvements,
                    "optimized_content": optimized_content,
                }

        logger.info(f"optimize_cv: using fallback for {job_role}")
        # Structured fallback — still applies the rules as best we can deterministically
        fallback_content = (
            f"## Summary\n"
            f"Experienced professional with expertise in {skills_str.split(',')[0].strip() if skills_str else 'relevant technologies'}, "
            f"applying for {job_role}.\n\n"
            f"## Skills\n"
            + "\n".join(f"- {s.strip()}" for s in skills_str.split(",") if s.strip()) + "\n\n"
            f"## Experience\n"
            f"{experience_str}\n\n"
            f"## Education\n"
            f"{education_str}"
        )
        return {
            "keyword_match_score": 60,
            "suggested_improvements": [
                "Replace weak verbs (helped, worked on) with strong action verbs (Led, Built, Delivered)",
                "Add scope or outcome to each bullet (e.g. '…serving 10K users')",
                "Remove filler phrases like 'passionate about' or 'team player'",
                "Tailor skills section to mirror exact keywords in the job description",
            ],
            "optimized_content": fallback_content,
        }

    def edit_cv_with_instruction(
        self,
        current_content: str,
        instruction: str,
        job_role: str = "",
    ) -> Dict[str, Any]:
        """Apply a user instruction to revise an existing CV, following resume_editor rules."""
        context = f"Target role: {job_role}\n" if job_role else ""
        prompt = f"""You are a professional resume editor. Apply the user's instruction to improve the CV below.

RESUME EDITOR RULES — always apply:
1. Replace weak verbs with strong action verbs (Led, Built, Designed, Delivered, Optimized, Automated, Managed, etc.)
2. Every bullet = WHAT was done + OUTCOME or SCOPE
3. Remove fluff ("passionate about", "team player", "hard-working") unless backed by evidence
4. Keep each bullet to max 2 lines
5. No fake metrics — only use numbers already in the original text
6. No invented achievements — only reframe what the candidate actually did

User instruction: {instruction}
{context}
Current CV:
{current_content[:3000]}

Return a JSON object with:
- revised_content (string): the full updated CV in Markdown, preserving all sections
- explanation (string): 1-2 sentences describing exactly what you changed

Respond with ONLY a valid JSON object."""

        text = _call_llm(prompt, max_tokens=4096)
        if text:
            data = _parse_json_from_llm(text)
            if data and "revised_content" in data:
                logger.info("edit_cv_with_instruction: LLM revision applied")
                return data

        logger.info("edit_cv_with_instruction: using fallback (no change)")
        return {
            "revised_content": current_content,
            "explanation": "AI edit unavailable — please rephrase your instruction or edit manually.",
        }

    def generate_email(
        self,
        job_role: str,
        company: str,
        cv_summary: str,
        hr_name: Optional[str] = None,
        matched_skills: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Generate a professional job application email under 200 words."""
        skills_str = ", ".join((matched_skills or [])[:5])
        greeting = f"Dear {hr_name}," if hr_name else "Dear Hiring Manager,"
        prompt = f"""Write a professional job application email. Requirements:
- Under 200 words total
- Start with: {greeting}
- Professional yet personable tone
- Mention 2-3 specific matched skills naturally
- End with a clear call to action
- NO generic filler phrases like "I am writing to express my interest"

Return a JSON object with:
- subject (string): compelling email subject line
- body (string): the complete email body

Job Role: {job_role}
Company: {company}
Candidate Summary: {cv_summary[:500]}
Matched Skills: {skills_str}

Respond with ONLY a JSON object."""

        text = _call_llm(prompt)
        if text:
            data = _parse_json_from_llm(text)
            if data and "subject" in data and "body" in data:
                logger.info(f"generate_email: LLM generated for {company} - {job_role}")
                return data

        logger.info(f"generate_email: using template fallback for {company}")
        return self._fallback_generate_email(job_role, company, cv_summary, hr_name)

    def edit_resume(self, resume_text: str) -> str:
        """Improve resume clarity, grammar, and bullet strength without fabricating."""
        prompt = f"""Edit this resume text to improve:
- Clarity and conciseness
- Grammar and professional tone
- Bullet point strength (use action verbs + quantifiable results where possible)

IMPORTANT: Do NOT add skills, experience, or achievements that are not already present.

Resume text:
{resume_text[:2000]}

Return ONLY the improved resume text, no explanation."""

        text = _call_llm(prompt, system="You are a professional resume editor.")
        if text and len(text) > 50:
            logger.info("edit_resume: LLM improved resume")
            return text

        logger.info("edit_resume: using passthrough fallback")
        return resume_text

    def generate_evidence(
        self,
        experience_item: Dict,
        target_skill: str,
    ) -> List[str]:
        """Generate evidence statements linking experience to a target skill."""
        role = experience_item.get("role", "professional")
        company = experience_item.get("company", "an organization")
        description = experience_item.get("description", "")
        prompt = f"""Generate 2-3 concise evidence statements that demonstrate '{target_skill}' skill based on this work experience.
Each statement should be one sentence, start with a strong action verb, and include specific context.

Role: {role}
Company: {company}
Description: {description[:500]}

Return a JSON object with:
- evidence (array of strings): the evidence statements

Respond with ONLY a JSON object."""

        text = _call_llm(prompt)
        if text:
            data = _parse_json_from_llm(text)
            if data and "evidence" in data and isinstance(data["evidence"], list):
                logger.info(f"generate_evidence: LLM generated {len(data['evidence'])} statements")
                return data["evidence"]

        return [f"Demonstrated {target_skill} skills as {role} at {company}."]

    def enforce_governance(
        self,
        mission_id: int,
        current_progress: int,
        target_count: int,
        daily_limit: int,
        applications_today: int,
    ) -> Dict[str, Any]:
        """Enforce governance rules per constitution.md §5.4 (rule-based)."""
        if current_progress >= target_count:
            return {"can_proceed": False, "reason": "Mission target already reached", "remaining_quota": 0}
        if applications_today >= daily_limit:
            return {"can_proceed": False, "reason": f"Daily application limit reached ({daily_limit})", "remaining_quota": 0}
        remaining = min(target_count - current_progress, daily_limit - applications_today)
        return {"can_proceed": True, "reason": "Governance check passed", "remaining_quota": remaining}

    def validate_email_content(
        self,
        email_subject: str,
        email_body: str,
        job_role: str,
        company: str,
    ) -> Dict[str, Any]:
        """Validate email content (rule-based word-count check)."""
        word_count = len(email_body.split())
        issues = ["Email exceeds 250 words"] if word_count > 250 else []
        return {"is_valid": len(issues) == 0, "issues": issues, "suggestions": []}

    def make_final_decision(
        self,
        context: str,
        question: str,
        options: List[str],
    ) -> str:
        """Make final decision (rule-based default — first option)."""
        return f"Option 1: {options[0] if options else 'proceed'} (rule-based default)"

    # ------------------------------------------------------------------ #
    # Rule-based fallback helpers                                         #
    # ------------------------------------------------------------------ #

    def _fallback_parse_mission(self, user_input: str) -> Dict[str, Any]:
        text = user_input.lower()

        count_match = re.search(
            r"(?:find|get|send|apply\s+(?:to|for))?\s*(\d+)\s*"
            r"(?:\w+\s+){0,3}(?:jobs?|applications?|positions?|roles?|openings?)",
            text,
        )
        if not count_match:
            nums = re.findall(r"\b(\d+)\b(?!\s*(?:days?|weeks?|months?|year))", text)
            count_val = int(nums[0]) if nums else 10
        else:
            count_val = int(count_match.group(1))
        target_count = min(max(count_val, 1), 50)

        days_match = re.search(r"(\d+)\s*days?", text)
        weeks_match = re.search(r"(\d+)\s*weeks?", text)
        months_match = re.search(r"(\d+)\s*months?", text)
        if days_match:
            time_days: Optional[int] = int(days_match.group(1))
        elif weeks_match:
            time_days = int(weeks_match.group(1)) * 7
        elif months_match:
            time_days = int(months_match.group(1)) * 30
        else:
            time_days = None

        location: Optional[str] = None
        for word in [
            "karachi", "lahore", "islamabad", "rawalpindi", "dubai", "abu dhabi",
            "london", "new york", "san francisco", "toronto",
            "remote", "onsite", "hybrid", "pakistan", "uk", "usa", "canada",
        ]:
            if word in text:
                location = word.title()
                break

        if "contract" in text:
            job_type = "Contract"
        elif "part-time" in text or "part time" in text:
            job_type = "Part-time"
        elif "remote" in text:
            job_type = "Remote"
        else:
            job_type = "Full-time"

        stop_pattern = (
            r"\b(i|want|to|find|get|apply|send|me|for|in|within|a|an|the|"
            r"jobs?|applications?|positions?|roles?|openings?|vacancies?|"
            r"\d+\s*(?:days?|weeks?|months?)|"
            r"\d+)\b"
        )
        role_text = re.sub(stop_pattern, " ", text, flags=re.IGNORECASE)
        if location:
            role_text = re.sub(r"\b" + re.escape(location.lower()) + r"\w*\b", " ", role_text)
        role_text = re.sub(
            r"\b(remotely?|onsitely?|hybridly?|contract|part.time|full.time)\b",
            " ", role_text, flags=re.IGNORECASE,
        )
        role_text = re.sub(r"\s+", " ", role_text).strip(" ,.")
        target_role = role_text.title() if role_text else "Software Developer"

        return {
            "target_role": target_role,
            "target_count": target_count,
            "time_constraint_days": time_days,
            "location_preference": location,
            "job_type": job_type,
        }

    def _fallback_parse_cv(self, cv_text: str) -> Dict[str, Any]:
        lines = [ln.strip() for ln in cv_text.split("\n") if ln.strip()]
        skills_keywords = [
            "python", "java", "javascript", "typescript", "react", "node", "django",
            "flask", "fastapi", "sql", "mysql", "postgresql", "mongodb", "redis",
            "docker", "kubernetes", "aws", "azure", "gcp", "git", "linux",
            "machine learning", "deep learning", "tensorflow", "pytorch",
        ]
        found_skills = [k.title() for k in skills_keywords if k in cv_text.lower()]
        return {
            "summary": lines[0] if lines else "Professional with industry experience.",
            "skills": found_skills or ["Communication", "Problem Solving"],
            "experience": [],
            "projects": [],
            "education": [],
        }

    def _fallback_generate_email(
        self,
        job_role: str,
        company: str,
        cv_summary: str,
        hr_name: Optional[str] = None,
    ) -> Dict[str, str]:
        greeting = f"Dear {hr_name}," if hr_name else "Dear Hiring Manager,"
        body = (
            f"{greeting}\n\n"
            f"I am excited to apply for the {job_role} role at {company}. "
            f"My background aligns well with your requirements, and I am confident "
            f"I can make a meaningful contribution to your team.\n\n"
            f"{cv_summary}\n\n"
            f"I have attached my resume and would welcome a conversation to discuss "
            f"how my experience meets your needs.\n\n"
            f"Thank you for your consideration.\n\nBest regards"
        )
        return {
            "subject": f"Application for {job_role} — {company}",
            "body": body,
        }
