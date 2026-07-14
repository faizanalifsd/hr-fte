---
name: cv_professional_template
description: Canonical professional CV structure/format, distilled from the user's real resume. Use whenever generating or reviewing a CV version in this project — both as a Claude Code skill and as the spec that backend/services/ai/llm_service.py's optimize_cv()/parse_cv() implement.
version: 1.0
token_budget: low
---

# PURPOSE

Defines the exact section structure, ordering, and tone that a generated CV
version must follow in this project. Distilled directly from the user's own
professional resume (`my Resume.pdf`) — this is the ground truth for "what a
professional CV looks like" here, not a generic template.

This spec is implemented in code at `backend/services/ai/llm_service.py`
(`optimize_cv()` prompt + its rule-based fallback). If either drifts from this
file, fix the code to match this file — not the other way around.

---

# REQUIRED SECTIONS (in this exact order)

1. **Header** — no heading label, just:
   ```
   [Full Name]
   Current Location: [City, Country]
   Contact: [Phone] | LinkedIn: [linkedin.com/in/...]
   Email: [email]
   ```
   Omit any line whose data isn't known — never invent a phone number, email, or
   LinkedIn URL that wasn't in the source CV.

2. **Opening pitch bullets** — no section header, 3-5 bullets directly under the
   header. Each bullet is a punchy, keyword-dense claim (role + specialization +
   proof), not a paragraph. This replaces a traditional "Summary" paragraph.

3. **PROFESSIONAL SKILLS:**
   - `Technical Skills:` — comma-separated list (languages, frameworks, concepts)
   - `Tools Skills:` — comma-separated list (dev tools, platforms, CLIs)
   Reorder both lists so the most job-relevant items come first when tailoring.

4. **PROFESSIONAL WORK EXPERIENCE:**
   For each role, in reverse chronological order:
   ```
   [Company Name]
   [Title] | [Duration]
   Roles & Responsibilities:
   - bullet
   - bullet
   Projects:
   - **[Project Name]**: [1-3 sentence description]
   ```
   Only include "Projects:" under a role if the source CV data actually has
   projects tied to it.

5. **KEY ACHIEVEMENTS:**
   3-5 high-level bullets pulled up from across all experience — the
   "if a recruiter reads only one section" summary. Distinct from the
   per-role bullets in Experience (don't just repeat them verbatim).

6. **EDUCATION:**
   ```
   [Degree] — [Institution]                    [Years]
   ```

7. **LANGUAGES:** — only include this section if the source CV actually states
   languages. Never fabricate.

---

# TONE / WRITING RULES

Same anti-AI-tell rules as [[resume_editor]]:
- Never use: Leverage/Leveraged, Additionally, Furthermore, Moreover, Spearheaded,
  Utilize, Demonstrated expertise, Proven track record, Passionate about, Dedicated to
- Mix bullet lengths and openers — not every bullet starts with the same verb pattern
- Use rough real numbers when present in the source data (~30%, 3-person team) —
  never invent metrics
- No superlatives ("best", "world-class", "top-tier")

---

# INTEGRITY RULES

- Never invent employer names, titles, dates, degrees, contact details, or metrics
- Only reframe/reorder what already exists in the parsed CV data
- If a section's source data is missing entirely (e.g. no languages, no projects
  for a role), omit that section/sub-section rather than filling it with filler

---

# WHY THIS MATTERS

Before this skill existed, the rule-based fallback path (triggered when Groq AND
OpenRouter both fail/rate-limit) produced a bare field dump with no header, no
structure, and none of the above sections — see the "not professional" CV issue
reported 2026-07-14. Both the LLM prompt and the deterministic fallback in
`llm_service.py` must produce this structure so quality doesn't regress when
providers are unavailable.
