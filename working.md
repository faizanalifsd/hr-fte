# HOW THIS SYSTEM WORKS
### Plain-English Guide to the AI Job Application Agent

---

## THE BIG PICTURE

Think of this system as a **digital employee (FTE = Full-Time Employee)** that works for you 24/7 doing job hunting. You tell it what job you want, give it your CV, and it:

1. Finds real job listings on LinkedIn (via Apify scraper)
2. Scores each job — how well does your CV match?
3. Rewrites your CV slightly to fit each job better
4. Writes a personalized email for each job
5. **Stops and waits for you to approve** every email before sending
6. Sends approved emails through your Gmail
7. Records everything with proof (timestamps, hashes)

You are always in control. **No email is ever sent without your approval.**

---

## THE TWO PARTS

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND (React)          BACKEND (Python/FastAPI)      │
│  http://localhost:5173  ←→  http://localhost:8003        │
│                                                          │
│  What you see & click       What actually does the work  │
└─────────────────────────────────────────────────────────┘
```

- **Frontend** = the website you open in your browser (React/Vite)
- **Backend** = the engine running behind the scenes (FastAPI/Python)
- They talk to each other via a REST API (HTTP requests/responses)

---

## THE DATABASE (MySQL)

7 tables store everything:

| Table               | What it stores                                      |
|---------------------|-----------------------------------------------------|
| `missions`          | Your job search goal (role, target count, location) |
| `jobs`              | Every job listing scraped from LinkedIn             |
| `cv_versions`       | Your master CV + one optimized version per job      |
| `email_drafts`      | AI-written emails waiting for your approval         |
| `application_records` | Permanent record of every email actually sent     |
| `audit_logs`        | Every action the system took (for accountability)   |
| `execution_states`  | Current phase of each workflow step                 |

---

## THE AI BRAIN

The system uses real AI APIs (not a local model):

```
OpenRouter (primary)  →  Groq (fallback)  →  Rule-based logic (last resort)
     ↓                        ↓                        ↓
llama-3.1-8b               llama-3.3-70b         Hardcoded templates
(free tier)               (ultra-fast)           (always works, no API)
```

If OpenRouter is busy or fails → tries Groq automatically.
If Groq also fails → uses simple rule-based templates. **The system never crashes due to AI failure.**

---

## THE 12 PHASES — STEP BY STEP

### PHASE 1 — Mission Initialization
**Who does it:** You (via frontend) + AI

You type something like:
> "Apply to 10 Python Developer jobs in London"

The AI parses this into structured data:
```json
{
  "target_role": "Python Developer",
  "target_count": 10,
  "location_preference": "London"
}
```
This gets saved to the `missions` table. Status = `Initialized`.

---

### PHASE 2 — CV Upload
**Who does it:** You

You paste your CV text (or upload a file) in the dialog box.
The system stores it. Mission status changes to `Running`.

---

### PHASE 3 — CV Parsing
**Who does it:** AI (OpenRouter/Groq)

The AI reads your CV and extracts structured info:
```json
{
  "skills": ["Python", "Django", "SQL", "Docker"],
  "experience": [{"role": "Backend Dev", "years": 3}],
  "education": "BSc Computer Science"
}
```
This structured data is used later for job matching and CV optimization.
Saved to `cv_versions` table as the **Master CV**.

---

### PHASE 4 — Job Scraping
**Who does it:** Apify (external scraper service)

The backend calls the **Apify API** with your job role and location.
Apify scrapes LinkedIn/job boards and returns real job listings.

Each listing gets saved to the `jobs` table with status = `Scraped`:
- Company name
- Job role/title
- Location
- Full job description
- Apply link
- HR contact (if found)

Retries up to 3 times if Apify fails.

---

### PHASE 5 — Job Selection
**Who does it:** Backend (automatic)

From all scraped jobs, the system randomly picks **5 jobs** to proceed with.
Each selected job gets status = `Selected`. All others are marked `Matched` (not pursued).

No scoring or AI matching is performed — the CV will be tailored to each selected job in Phase 6.

---

### PHASE 6 — CV Versioning
**Who does it:** AI (OpenRouter/Groq)

For every selected job, the AI creates a **tailored version of your CV**:
- Adds keywords from the job description
- Reorders bullet points to highlight relevant experience
- **Never fabricates — only rearranges/emphasizes what's already there**

Each version saved to `cv_versions` with a link to the specific job.

---

### PHASE 7 — Email Generation
**Who does it:** AI (OpenRouter/Groq)

For every selected job, the AI writes a **personalized application email** (< 200 words):
- Professional tone
- Mentions the company and role specifically
- Highlights your top matching skills
- Addressed to the HR person if their name was found

Email saved to `email_drafts` with status = `PendingApproval`.
**The email is NOT sent yet.**

---

### PHASE 8 — Human Approval (HITL)
**Who does it:** YOU

This is the mandatory human checkpoint. The frontend shows you every email draft.

You have 3 choices for each email:
- ✅ **Approve** → email will be sent as-is
- ✏️ **Edit** → modify the email, then approve
- ❌ **Reject** → skip this job entirely

**Nothing gets sent until you approve it. This is enforced by the system — it's not optional.**

---

### PHASE 9 — Application Sending
**Who does it:** Gmail API

For approved emails, the backend:
1. Checks governance rules (daily limit = 20 max per day)
2. Sends the email via your **Gmail account** with the tailored CV attached
3. Gets a Gmail message ID as proof
4. Creates a permanent record in `application_records` with:
   - Gmail message ID
   - Timestamp
   - SHA-256 hash of the email content (tamper-proof)

Job status → `Applied`. Mission progress count goes up by 1.

Retries up to 3 times if Gmail fails.

---

### PHASE 10 — Evidence & Audit
**Who does it:** Backend (automatic)

Every single action is logged to `audit_logs`:
- Which agent did what
- When exactly
- What the result was
- Any errors

The email content is hashed (SHA-256) — you can prove exactly what was sent, to whom, and when.

---

### PHASE 11 — Mission Validation
**Who does it:** Backend (automatic)

Checks if you've hit your target:
```
If applications_sent >= target → Mission = Completed
If unrecoverable error         → Mission = Failed
Otherwise                      → Mission = Running (keep going)
```

---

### PHASE 12 — Graph Update
**Who does it:** Frontend (polling every 5 seconds)

The frontend polls the backend every 5 seconds to show live status:
- Which phases are done (green)
- Which are running (blue)
- Which failed (red)
- Which are pending (gray)

---

## HOW THE FRONTEND IS ORGANIZED

```
src/
├── pages/
│   └── Index.tsx           ← Main page, holds all state
├── components/
│   ├── AIControlPanel.tsx  ← Shows live audit log (what the AI is doing right now)
│   ├── AgentMonitor.tsx    ← Shows mission progress + phase status
│   ├── JobFeed.tsx         ← Shows scraped + matched jobs
│   ├── EvidenceTab.tsx     ← Shows all sent applications with proof
│   ├── PlanTab.tsx         ← Shows the job plan / start a mission
│   ├── MissionLaunchDialog.tsx  ← Dialog to enter mission + paste CV
│   └── HITLApprovalPanel.tsx   ← Approve/reject/edit email drafts
├── hooks/
│   └── useAutonomous.ts    ← All API calls + mission state management
└── lib/
    └── api.ts              ← Typed API client (talks to backend)
```

---

## HOW THE BACKEND IS ORGANIZED

```
backend/
├── app.py                  ← FastAPI app entry point, startup validation
├── models/
│   └── __init__.py         ← All database tables (SQLAlchemy ORM)
├── routes/
│   ├── missions.py         ← POST /api/missions/, GET /api/missions/{id}
│   ├── jobs.py             ← GET /api/jobs/mission/{id}
│   ├── emails.py           ← GET /api/emails/pending, POST approve/reject
│   └── applications.py     ← POST /api/applications/send
└── services/
    ├── orchestrator.py     ← Master 12-phase workflow controller
    ├── ai/
    │   ├── llm_service.py  ← OpenRouter → Groq → Rule-based AI
    │   └── ollama_service.py ← Thin alias to llm_service (backward compat)
    └── mcp/
        ├── apify_service.py ← Calls Apify API to scrape jobs
        └── gmail_service.py ← Calls Gmail API to send emails
```

---

## API ENDPOINTS (Backend ↔ Frontend)

| Method | URL                            | What it does                              |
|--------|--------------------------------|-------------------------------------------|
| POST   | /api/missions/                 | Create a new mission                      |
| GET    | /api/missions/                 | List all missions                         |
| GET    | /api/missions/{id}             | Get one mission's status + progress       |
| POST   | /api/missions/{id}/execute     | Start the full 12-phase workflow          |
| GET    | /api/missions/{id}/audit       | Get audit log (frontend polls this)       |
| GET    | /api/jobs/mission/{id}         | Get all jobs for a mission                |
| GET    | /api/emails/pending            | Get emails waiting for your approval      |
| POST   | /api/emails/{id}/approve       | Approve an email                          |
| POST   | /api/emails/{id}/reject        | Reject an email                           |
| PATCH  | /api/emails/{id}               | Edit an email draft                       |
| POST   | /api/applications/send         | Send an approved application              |
| GET    | /api/applications/             | List all sent applications                |

---

## THE GOVERNANCE RULES (Constitution)

These rules are hardcoded and cannot be bypassed:

1. **No email sent without human approval** — HITL is mandatory (Phase 8)
2. **Max 20 applications per day** — enforced before every send (Phase 9)
3. **No fabrication** — AI only rearranges/emphasizes, never invents experience
4. **Full audit trail** — every action logged with timestamp
5. **Retry policy** — max 3 attempts, waits 2s/4s/8s between retries
6. **Single job failure doesn't stop the workflow** — it logs and continues

---

## STEP-BY-STEP: WHAT TO DO TO RUN A MISSION

1. Open browser → `http://localhost:5173`
2. Click the **"Autonomous"** toggle
3. A dialog appears → enter your job goal (e.g., "10 Python jobs in London")
4. Paste your CV text
5. Click **"Launch Mission"**
6. Watch the **Agent Monitor** and **AI Control Panel** — the system starts working
7. After a few minutes, the **HITL panel** appears with email drafts
8. Review each email → Approve / Edit / Reject
9. Approved emails are sent automatically via Gmail
10. Check **Evidence tab** to see sent applications with proof

---

## COMMON STATUS VALUES

**Mission status:**
- `Initialized` → Created, not started yet
- `Running` → Actively working through phases
- `Completed` → Hit the target application count
- `Failed` → Unrecoverable error occurred

**Job status:**
- `Scraped` → Found by Apify, not selected yet
- `Matched` → Reviewed but not selected
- `Selected` → Randomly picked to apply
- `CV_Optimized` → Tailored CV created
- `Email_Drafted` → Email written, waiting approval
- `Approved` → You approved the email
- `Applied` → Email sent successfully
- `Rejected` → You rejected it, or score too low
- `Failed` → Send failed after 3 retries

**Email status:**
- `PendingApproval` → Waiting for you to review
- `Approved` → You approved it
- `Rejected` → You rejected it
- `Sent` → Successfully delivered via Gmail

---

*Last updated: 2026-03-02*
