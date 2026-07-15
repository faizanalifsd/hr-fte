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
- name (string or null): candidate's full name
- location (string or null): current city/country, e.g. "Lahore, Pakistan"
- phone (string or null): contact phone number
- email (string or null): contact email
- linkedin (string or null): LinkedIn profile URL
- summary (string): one-sentence professional summary
- skills (array of strings): technical and professional skills
- tools (array of strings): dev tools, platforms, CLIs (separate from core technical skills)
- experience (array of objects with role, company, duration, description, projects — projects is an array of objects with name, description, tied to that role if any)
- key_achievements (array of strings): 3-5 high-level standout accomplishments across the whole CV
- education (array of objects with degree, institution, year)
- languages (array of objects with language, proficiency) — omit/empty if not stated
- projects (array of objects with name, description, technologies) — standalone projects not tied to a specific role

Only extract what is explicitly present. Use null/empty for anything not stated — never invent contact details, dates, or achievements.

CV text:
{cv_text[:8000]}

Respond with ONLY a JSON object."""

        text = _call_llm(prompt, max_tokens=2048)
        if text:
            data = _parse_json_from_llm(text)
            if data and "skills" in data:
                logger.info(f"parse_cv: LLM extracted {len(data.get('skills', []))} skills")
                return data

        logger.info("parse_cv: using rule-based fallback")
        return self._fallback_parse_cv(cv_text)

    def score_job_match(
        self,
        cv_data: Dict,
        job_role: str,
        job_description: str,
    ) -> Dict[str, Any]:
        """
        Score how well a candidate's real skills/experience fit a specific job.
        Used by Phase 5 job selection so only genuinely relevant jobs get a
        tailored CV — replaces the old random.sample() placeholder.
        """
        skills = cv_data.get("skills", []) + cv_data.get("tools", [])
        skills_str = ", ".join(skills[:25]) or "Not provided"
        experience_lines = []
        for exp in cv_data.get("experience", [])[:5]:
            role = exp.get("role", "")
            desc = exp.get("description", "")
            experience_lines.append(f"- {role}: {desc}")
        experience_str = "\n".join(experience_lines) or "Not provided"

        prompt = f"""Score how well this candidate's REAL skills and experience match the job below. Be honest and strict — this determines whether their CV even gets tailored for this job, so don't inflate the score for a poor fit.

Candidate Skills: {skills_str}
Candidate Experience:
{experience_str}

Job Role: {job_role}
Job Description: {job_description[:1200]}

Return a JSON object with:
- match_score (integer 0-100): overall fit based on real overlap between candidate skills/experience and job requirements
- matched_skills (array of strings): candidate skills that genuinely apply to this job
- missing_skills (array of strings): job requirements the candidate does not have
- experience_alignment (string): "high", "medium", or "low"

Respond with ONLY a JSON object."""

        text = _call_llm(prompt, max_tokens=512)
        if text:
            data = _parse_json_from_llm(text)
            if data and "match_score" in data:
                try:
                    data["match_score"] = max(0, min(int(data["match_score"]), 100))
                    data.setdefault("matched_skills", [])
                    data.setdefault("missing_skills", [])
                    data.setdefault("experience_alignment", "low")
                    return data
                except (ValueError, TypeError):
                    pass

        logger.info(f"score_job_match: using rule-based fallback for '{job_role}'")
        return self._fallback_score_job_match(skills, job_role, job_description)

    def _fallback_score_job_match(
        self,
        candidate_skills: List[str],
        job_role: str,
        job_description: str,
    ) -> Dict[str, Any]:
        """Deterministic keyword-overlap scoring — no LLM required."""
        haystack = f"{job_role} {job_description}".lower()
        matched = [s for s in candidate_skills if s.lower() in haystack]
        missing: List[str] = []  # can't know real job requirements without an LLM read
        skill_count = len(candidate_skills) or 1
        overlap_ratio = len(matched) / skill_count
        match_score = min(int(overlap_ratio * 100), 100)
        alignment = "high" if match_score >= 60 else "medium" if match_score >= 30 else "low"
        return {
            "match_score": match_score,
            "matched_skills": matched,
            "missing_skills": missing,
            "experience_alignment": alignment,
        }

    def optimize_cv(
        self,
        cv_data: Dict,
        job_description: str,
        job_role: str,
    ) -> Dict[str, Any]:
        """Optimize CV content for a specific job.

        Output follows the cv_professional_template skill
        (.claude/skills/cv_professional_template/SKILL.md) — header with contact
        info, unlabeled pitch bullets, PROFESSIONAL SKILLS:, PROFESSIONAL WORK
        EXPERIENCE: (with Roles & Responsibilities / Projects), KEY ACHIEVEMENTS:,
        EDUCATION:, and LANGUAGES: (only if present). Both the LLM prompt and the
        deterministic fallback below must stay in sync with that file.
        """
        name = cv_data.get("name") or ""
        location = cv_data.get("location") or ""
        phone = cv_data.get("phone") or ""
        email = cv_data.get("email") or ""
        linkedin = cv_data.get("linkedin") or ""
        skills_str = ", ".join(cv_data.get("skills", [])[:20])
        tools_str = ", ".join(cv_data.get("tools", [])[:20])
        summary = cv_data.get("summary", "")
        key_achievements = cv_data.get("key_achievements", [])[:5]
        languages = cv_data.get("languages", [])

        # Serialise experience / education / projects for the prompt
        experience_lines = []
        for exp in cv_data.get("experience", [])[:5]:
            role = exp.get("role", "")
            company = exp.get("company", "")
            duration = exp.get("duration", "")
            desc = exp.get("description", "")
            experience_lines.append(f"- {role} at {company} ({duration}): {desc}")
            for proj in exp.get("projects", []) or []:
                if isinstance(proj, dict):
                    experience_lines.append(f"  - project tied to this role: {proj.get('name','')}: {proj.get('description','')}")
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

        header_lines = [name] if name else []
        if location:
            header_lines.append(f"Current Location: {location}")
        contact_bits = []
        if phone:
            contact_bits.append(phone)
        if linkedin:
            contact_bits.append(f"LinkedIn: {linkedin}")
        if contact_bits:
            header_lines.append("Contact: " + " | ".join(contact_bits))
        if email:
            header_lines.append(f"Email: {email}")
        header_str = "\n".join(header_lines) or "Not provided — omit header lines with no data"

        languages_str = "\n".join(
            f"- {lg.get('language','')}: {lg.get('proficiency','')}" if isinstance(lg, dict) else f"- {lg}"
            for lg in languages
        )
        key_achievements_str = "\n".join(f"- {a}" for a in key_achievements)

        prompt = f"""You are a professional resume writer. Rewrite the candidate's CV perfectly tailored for the target job, following the EXACT structure below. It must read like a human wrote it — a recruiter must not detect AI authorship.

=== TAILORING RULES ===
1. Mirror the job description's exact keywords, tools, and terminology throughout
2. Rewrite every experience bullet using the job's language — past roles must sound directly relevant
3. Reorder Skills/Tools so the most job-relevant items appear first
4. Write the opening pitch bullets as a natural pitch mentioning the job title organically
5. Never invent metrics, titles, experiences, or contact details — only reframe what already exists

=== ANTI-AI RULES ===
NEVER use: "Leverage/Spearheaded/Utilize/Additionally/Furthermore/Results-driven/Proven track record/Passionate about/Dedicated to"
ALWAYS: Mix bullet lengths, vary openers, use rough numbers (~30%, 3-person team) only if present in input, no superlatives

=== REQUIRED CV STRUCTURE (follow exactly, omit any line/section with no source data — never fabricate) ===
[Name]
Current Location: [City, Country]
Contact: [Phone] | LinkedIn: [linkedin url]
Email: [email]

- [pitch bullet 1 — no header, 3-5 punchy bullets mixing role, specialization, and proof]
- [pitch bullet ...]

PROFESSIONAL SKILLS:
Technical Skills:
[comma-separated list, most job-relevant first]
Tools Skills:
[comma-separated list, most job-relevant first]

PROFESSIONAL WORK EXPERIENCE:
[Company Name]
[Title] | [Duration]
Roles & Responsibilities:
- bullet
- bullet
Projects:
- **[Project Name]**: [description] (only include if this role actually has projects)

KEY ACHIEVEMENTS:
- [3-5 high-level bullets distinct from the per-role bullets above]

EDUCATION:
- [Degree] — [Institution] ([Years])
(omit this entire section — heading included — if no education was provided; NEVER write a placeholder like "No education information provided")

LANGUAGES:
- [Language]: [Proficiency]
(omit this entire section — heading included — if no languages were provided; NEVER write a placeholder like "No language information provided")

=== OUTPUT FORMAT (CRITICAL — follow exactly) ===
Line 1: SCORE:<integer 0-100>
Line 2: IMPROVEMENTS:<improvement1>|<improvement2>|<improvement3>
Line 3: (blank)
Lines 4+: The complete tailored CV following the REQUIRED CV STRUCTURE above

=== INPUT ===
Job Role: {job_role}
Job Description: {job_description[:1200]}

Candidate Header:
{header_str}

Pitch/Summary source: {summary}
Skills: {skills_str}
Tools: {tools_str}
Experience:
{experience_str}
Education:
{education_str}
{f"Standalone Projects:{chr(10)}{projects_str}" if projects_str else ""}
{f"Key Achievements (source):{chr(10)}{key_achievements_str}" if key_achievements_str else ""}
{f"Languages:{chr(10)}{languages_str}" if languages_str else ""}"""

        text = _call_llm(prompt, max_tokens=4096)
        if text:
            lines = text.strip().splitlines()
            score = None
            improvements = []
            improvements_idx = None
            for i, line in enumerate(lines):
                if line.startswith("SCORE:"):
                    try:
                        score = int(re.search(r"\d+", line).group())
                    except Exception:
                        pass
                elif line.startswith("IMPROVEMENTS:"):
                    improvements = [s.strip() for s in line[len("IMPROVEMENTS:"):].split("|") if s.strip()]
                    improvements_idx = i
            cv_start = 0
            if improvements_idx is not None:
                cv_start = improvements_idx + 1
                while cv_start < len(lines) and not lines[cv_start].strip():
                    cv_start += 1
            optimized_content = "\n".join(lines[cv_start:]).strip() if cv_start else ""
            if score is not None and optimized_content:
                logger.info(f"optimize_cv: LLM optimized full CV for {job_role} (score={score})")
                return {
                    "keyword_match_score": score,
                    "suggested_improvements": improvements,
                    "optimized_content": optimized_content,
                }

        logger.info(f"optimize_cv: using fallback for {job_role}")
        # Structured fallback — follows cv_professional_template deterministically
        fallback_sections = []
        if header_lines:
            fallback_sections.append("\n".join(header_lines))
        pitch = summary or (f"{cv_data.get('experience', [{}])[0].get('role','Professional')} applying for {job_role}." if cv_data.get("experience") else f"Professional applying for {job_role}.")
        fallback_sections.append(f"- {pitch}")
        if skills_str or tools_str:
            skills_block = "PROFESSIONAL SKILLS:\n"
            if skills_str:
                skills_block += "Technical Skills:\n" + skills_str + "\n"
            if tools_str:
                skills_block += "Tools Skills:\n" + tools_str
            fallback_sections.append(skills_block.strip())

        experience_blocks = []
        for exp in cv_data.get("experience", [])[:5]:
            role = exp.get("role", "")
            company = exp.get("company", "")
            duration = exp.get("duration", "")
            desc = exp.get("description", "")
            block_lines = [company, f"{role} | {duration}", "Roles & Responsibilities:"]
            desc_bullets = [s.strip() for s in re.split(r"(?<=[.!?])\s+", desc) if s.strip()] or ["Not provided"]
            block_lines += [f"- {b}" for b in desc_bullets]
            role_projects = exp.get("projects", []) or []
            if role_projects:
                block_lines.append("Projects:")
                for proj in role_projects:
                    if isinstance(proj, dict):
                        block_lines.append(f"- **{proj.get('name','')}**: {proj.get('description','')}")
            experience_blocks.append("\n".join(block_lines))
        fallback_sections.append(
            "PROFESSIONAL WORK EXPERIENCE:\n" + ("\n\n".join(experience_blocks) if experience_blocks else "Not provided")
        )

        if key_achievements_str:
            fallback_sections.append(f"KEY ACHIEVEMENTS:\n{key_achievements_str}")
        if education_lines:
            fallback_sections.append(f"EDUCATION:\n{education_str}")
        if languages_str:
            fallback_sections.append(f"LANGUAGES:\n{languages_str}")
        fallback_content = "\n\n".join(fallback_sections)

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
        tools_keywords = [
            "vs code", "vscode", "github", "gitlab", "postman", "figma", "jira",
            "n8n", "obsidian", "docusaurus", "claude code", "claude cli",
        ]
        found_skills = [k.title() for k in skills_keywords if k in cv_text.lower()]
        found_tools = [k.title() for k in tools_keywords if k in cv_text.lower()]

        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", cv_text)
        phone_match = re.search(r"\+?\d[\d\s\-()]{8,}\d", cv_text)
        linkedin_match = re.search(r"(?:linkedin\.com/in/[\w-]+)", cv_text, re.IGNORECASE)

        name = None
        for ln in lines[:3]:
            if len(ln) < 50 and not any(c in ln for c in ("@", "http", "+")) and re.match(r"^[A-Za-z][A-Za-z .'-]+$", ln):
                name = ln
                break

        return {
            "name": name,
            "location": None,
            "phone": phone_match.group() if phone_match else None,
            "email": email_match.group() if email_match else None,
            "linkedin": linkedin_match.group() if linkedin_match else None,
            "summary": lines[1] if len(lines) > 1 else (lines[0] if lines else "Professional with industry experience."),
            "skills": found_skills or ["Communication", "Problem Solving"],
            "tools": found_tools,
            "experience": [],
            "key_achievements": [],
            "projects": [],
            "education": [],
            "languages": [],
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
