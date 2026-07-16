# DIGITAL FTE EXECUTION PLAN
Version: 4.2 (Groq Primary + OpenRouter Fallback)
Last Updated: 2026-07-16
Architecture: LLM Sub-Agents + MCP + MySQL Persistence

---

## ARCHITECTURE OVERVIEW

1. **AI Sub-Agents** → Groq (primary) → OpenRouter (fallback) → Rule-based (final fallback)
2. **MCP Layer** → Secure External Tool Connectors (Apify for job scraping, Anymail Finder/Hunter.io/Snov.io/website-scrape waterfall for HR email discovery, Gmail for sending)
3. **MySQL** → Persistent Storage Layer

### LLM Provider Strategy:

| Priority | Provider     | Model                                     | Use Case                                |
|----------|--------------|--------------------------------------------|-------------------------------------------|
| 1        | Groq         | llama-3.3-70b-versatile                    | All AI tasks (fast, reliable free tier)   |
| 2        | OpenRouter   | meta-llama/llama-3.3-70b-instruct:free     | Fallback (used when Groq unavailable)     |
| 3        | Rule-based   | Deterministic logic                        | Final fallback (no API required)          |

Groq is primary because the OpenRouter free tier is frequently rate-limited; Groq's free tier has proven more reliable in practice.

### Role Assignment:

**AI Sub-Agents (backend/services/ai/llm_service.py):**
- Mission parsing
- CV parsing & optimization (contact info, skills, tools, experience, key achievements, education, languages)
- Job relevance scoring (`score_job_match`)
- Email generation
- Evidence generation
- Resume editing
- Email validation
- Structured content generation

**Python Backend (orchestrator.py):**
- Master 12-phase workflow coordination
- MCP tool invocation (Apify, Gmail)
- Database operations
- HITL validation
- Audit logging

### Security Rules:

- Only Backend Orchestrator may invoke MCP tools
- AI sub-agents do not directly access external APIs
- All API calls go through controlled backend services

---

## ENVIRONMENT VARIABLES & MCP CONFIGURATION

**Required Configuration:**

```env
# MCP Services
APIFY_API_KEY=<secure_key>
GMAIL_CLIENT_ID=<client_id>
GMAIL_CLIENT_SECRET=<client_secret>
GMAIL_REFRESH_TOKEN=<refresh_token>

# Database
DATABASE_URL=<connection_string>
```

**AI Provider Configuration (at least one required):**

```env
# Groq — Primary LLM provider (ultra-fast, reliable free tier)
# Models: llama-3.3-70b-versatile, llama-3.1-8b-instant, mixtral-8x7b-32768
GROQ_API_KEY=<secure_key>
GROQ_BASE_URL=https://api.groq.com/openai/v1

# OpenRouter — Fallback LLM provider (200+ models, free tier available)
# Models: meta-llama/llama-3.3-70b-instruct:free
OPENROUTER_API_KEY=<secure_key>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

**HR Email Discovery Providers (optional, waterfall — used in Phase 4b):**

```env
ANYMAILFINDER_API_KEY=<secure_key>
HUNTER_API_KEY=<secure_key>
SNOV_CLIENT_ID=<secure_key>
SNOV_CLIENT_SECRET=<secure_key>
```

If none are configured, or all fail for a given company, the system falls back to a free domain guesser + website scrape — never to a fabricated address. Confidence is recorded per lookup (`verified` / `likely` / none) and gates HITL approval (see constitution.md §3.5).

### Rules:

- No API keys stored in source code
- No API keys stored in database
- All keys loaded at runtime via os.getenv()
- System degrades gracefully: Groq → OpenRouter → Rule-based
- If all providers fail → rule-based fallback ensures continuity
- .env file is excluded from version control via .gitignore

---

## DATABASE CONNECTION LAYER

```env
DATABASE_URL=mysql+pymysql://user:password@host:port/database
```

Or individual parameters:

```env
DB_HOST=localhost
DB_USER=username
DB_PASS=password
DB_NAME=job_application_db
```

---

## PHASE 1 – MISSION INITIALIZATION

1. User submits Mission Objective
2. **AI Sub-Agent (Groq/OpenRouter)** parses: target role, target count, time constraint, location, job type
3. **Backend** inserts Mission record in database
4. Status = Initialized

**AI:** LLMService (Groq primary → OpenRouter fallback → rule-based)
**Backend Role:** Database operations, coordination

---

## PHASE 2 – CV UPLOAD

1. User uploads CV
2. **Backend** stores file securely
3. Update Mission.status = Running
4. Log action to AuditLog

**AI:** None (file operations)

---

## PHASE 3 – CV PARSING

**AI Sub-Agent (Groq/OpenRouter)** extracts structured data from the full CV text (up to 8000 chars — enough to cover education/languages sections near the end of longer resumes):
- Contact info: name, location, phone, email, linkedin
- Summary, skills, tools
- Experience (with role-tied projects), key achievements
- Education, languages, projects
- Returns structured JSON

If no LLM is reachable, `_fallback_parse_cv()` regex-extracts email/phone/linkedin/name so the pipeline never produces an empty profile.

**Backend:** Stores in CVVersion table, logs to AuditLog

---

## PHASE 4 – JOB SCRAPING

**Flow:** Backend → Apify MCP → Apify API

1. **Backend** constructs job query
2. **Backend** invokes Apify MCP using APIFY_API_KEY
3. Retrieve job listings
4. Normalize and insert into Job table
5. Log to AuditLog

Retry up to 3 times with exponential backoff.

**AI:** None (MCP operation)

---

## PHASE 4b – HR EMAIL DISCOVERY

**Flow:** Backend → `apollo_service.find_hr_email()` waterfall

1. Resolve company domain (Hunter domain search, or free `_guess_domain()` candidate/TLD guesser if that fails)
2. Try in order until one succeeds: **Anymail Finder → Hunter.io → Snov.io (v2 async: start + poll) → website scrape**
3. Record `hr_email_confidence` on the Job: `verified` (Anymail/Hunter with verification), `likely` (Snov/scrape or HR-prefixed local-part match), or none
4. Never fabricate an address (e.g. guessed `jobs@company.com`) — if the waterfall finds nothing, the job proceeds with no confirmed recipient and email approval is blocked (constitution.md §3.5) until the user supplies/edits a real one.

---

## PHASE 5 – JOB MATCHING

**AI Sub-Agent (Groq/OpenRouter)** scores every scraped job against the parsed CV via `score_job_match()`:
- Returns `match_score` (0-100), `matched_skills`, `missing_skills`, `experience_alignment`
- Deterministic keyword-overlap fallback (`_fallback_score_job_match`) when no LLM is reachable

**Backend selection logic (`orchestrator.match_jobs`, `MIN_RELEVANCE_SCORE = 40`):**
- Jobs are scored, then sorted by score descending
- Up to 5 jobs clearing the 40% relevance bar are selected (fewer if fewer qualify — the mission never force-selects irrelevant jobs just to hit a count)
- Jobs below the bar, or not selected among ties, are recorded as `Matched` (seen, not pursued) with their real score — never randomly chosen

This replaced an earlier version that randomly sampled 5 jobs regardless of fit (see constitution.md §9.5 — relevance gating is now a governance rule, not just an implementation detail).

---

## PHASE 6 – CV VERSIONING

**AI Sub-Agent (Groq/OpenRouter)** optimizes CV per job, enforcing the canonical professional structure (see `.claude/skills/cv_professional_template/SKILL.md`):
- Header (name + contact info), unlabeled pitch bullets
- PROFESSIONAL SKILLS (Technical/Tools split)
- PROFESSIONAL WORK EXPERIENCE (Roles & Responsibilities / Projects)
- KEY ACHIEVEMENTS
- EDUCATION, LANGUAGES — included when present in the parsed CV, entire section omitted (not printed as "Not provided") when absent
- Rearranges/emphasizes existing content only — never fabricates skills or experience to force a fit (constitution.md §9.6)

**Backend:** Stores in CVVersion table

---

## PHASE 7 – EMAIL GENERATION

**AI Sub-Agent (Groq/OpenRouter)** drafts email (< 200 words):
- Professional tone
- Personalized to role/company
- Returns subject + body

**Backend:** Stores in EmailDraft table, sets status = PendingApproval, sets `recipient_confirmed = True` only if `hr_email_confidence` is `verified` or `likely` (see Phase 4b)

---

## PHASE 8 – HUMAN APPROVAL (HITL)

User actions via frontend:
- **Approve** → EmailDraft.status = Approved (blocked with `RecipientNotConfirmedError` / HTTP 400 if `recipient_confirmed` is false — user must fix the recipient first)
- **Edit** → Modify content and/or `to_email`; editing `to_email` sets `recipient_confirmed = True`
- **Reject** → EmailDraft.status = Rejected, log reason

As per constitution.md §3: No email sent without explicit human approval, and no approval without a confirmed real recipient (§3.5).

---

## PHASE 9 – APPLICATION SENDING

**Flow:** Backend → Gmail MCP → Gmail API

1. Validate email is approved
2. Governance checks (daily limit, mission progress)
3. Gmail MCP sends email with CV attachment
4. Create ApplicationRecord (SHA-256 hash)
5. Update Job.status = Applied
6. Increment Mission.progress_count

Retry 3 times with exponential backoff.

---

## PHASE 10 – EVIDENCE & AUDIT

Immutable records:
- Gmail message_id
- Timestamp
- Email content hash (SHA-256)
- AuditLog entries

---

## PHASE 11 – MISSION VALIDATION

```python
if mission.progress_count >= mission.target_count:
    mission.status = Completed
elif has_unrecoverable_error:
    mission.status = Failed
else:
    mission.status = Running
```

---

## PHASE 12 – RUNTIME GRAPH UPDATE

Database-driven state visualization from ExecutionState, Job, Mission tables.

Node colors: Completed=Green, Running=Blue, Failed=Red, Pending=Gray

---

## GOVERNANCE ENFORCEMENT

Per constitution.md §5.4:
- Default: 20 applications per day
- Enforced before Phase 9

```python
if progress >= target:          return cannot_proceed
if applications_today >= limit: return cannot_proceed
remaining = min(target - progress, limit - applications_today)
```

---

## FAILURE CONTAINMENT

- Single job failure: log, continue with rest
- Retry policy: max 3 attempts, backoff 2s/4s/8s
- Critical failures: DB loss, MCP auth failure, missing required env var
- LLM failure: Groq → OpenRouter → rule-based (never blocks pipeline)

---

END OF EXECUTION PLAN

**Last Updated:** 2026-07-16 — Groq primary/OpenRouter fallback (corrected to match runtime), real relevance-scored job matching (Phase 5), HR email discovery waterfall + recipient-confirmation gate (Phase 4b/7/8), CV parsing/versioning now covers education/languages/contact info
**Version:** 4.2
