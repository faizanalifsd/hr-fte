# DIGITAL FTE EXECUTION PLAN
Version: 4.1 (OpenRouter Primary + Groq Fallback)
Architecture: LLM Sub-Agents + MCP + MySQL Persistence

---

## ARCHITECTURE OVERVIEW

1. **AI Sub-Agents** → OpenRouter (primary) → Groq (fallback) → Rule-based (final fallback)
2. **MCP Layer** → Secure External Tool Connectors (Apify, Gmail)
3. **MySQL** → Persistent Storage Layer

### LLM Provider Strategy:

| Priority | Provider     | Model                                 | Use Case                         |
|----------|--------------|---------------------------------------|----------------------------------|
| 1        | OpenRouter   | meta-llama/llama-3.1-8b-instruct:free | All AI tasks (200+ models)       |
| 2        | Groq         | llama-3.3-70b-versatile               | Fallback (ultra-fast inference)  |
| 3        | Rule-based   | Deterministic logic                   | Final fallback (no API required) |

### Role Assignment:

**AI Sub-Agents (backend/services/ai/llm_service.py):**
- Mission parsing
- CV parsing & optimization
- Email generation
- Job matching & scoring
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
# OpenRouter — Primary LLM provider (200+ models, free tier available)
# Models: meta-llama/llama-3.1-8b-instruct:free, google/gemma-2-9b-it:free
OPENROUTER_API_KEY=<secure_key>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Groq — Fallback LLM provider (ultra-fast free tier)
# Models: llama-3.3-70b-versatile, llama-3.1-8b-instant, mixtral-8x7b-32768
GROQ_API_KEY=<secure_key>
GROQ_BASE_URL=https://api.groq.com/openai/v1
```

### Rules:

- No API keys stored in source code
- No API keys stored in database
- All keys loaded at runtime via os.getenv()
- System degrades gracefully: OpenRouter → Groq → Rule-based
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

**AI Sub-Agent (Groq/OpenRouter)** extracts structured data:
- Skills, experience, projects, education, keywords
- Returns structured JSON

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

## PHASE 5 – JOB MATCHING

**AI Sub-Agent (Groq/OpenRouter)** scores jobs:
- Skills match: 40%
- Experience relevance: 30%
- Tech stack overlap: 20%
- Role alignment: 10%

**Backend threshold logic:**
- Score >= 80: Apply
- Score 60-79: Optimize First
- Score < 60: Skip

---

## PHASE 6 – CV VERSIONING

**AI Sub-Agent (Groq/OpenRouter)** optimizes CV per job:
- Extract keywords from description
- Suggest improvements (no fabrication)
- Return optimized content

**Backend:** Stores in CVVersion table

---

## PHASE 7 – EMAIL GENERATION

**AI Sub-Agent (Groq/OpenRouter)** drafts email (< 200 words):
- Professional tone
- Personalized to role/company
- Returns subject + body

**Backend:** Stores in EmailDraft table, sets status = PendingApproval

---

## PHASE 8 – HUMAN APPROVAL (HITL)

User actions via frontend:
- **Approve** → EmailDraft.status = Approved
- **Edit** → Modify, track edit_count
- **Reject** → EmailDraft.status = Rejected, log reason

As per constitution.md §3: No email sent without explicit human approval.

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
- LLM failure: OpenRouter → Groq → rule-based (never blocks pipeline)

---

END OF EXECUTION PLAN

**Last Updated:** 2026-03-02 — OpenRouter primary, Groq fallback, no Anthropic key
**Version:** 4.1
