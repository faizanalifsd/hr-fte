# HOW THIS SYSTEM WORKS
### Plain-English Guide to the AI Job Application Agent

---

## THE BIG PICTURE

Think of this system as a **digital employee (FTE = Full-Time Employee)** that works for you 24/7 doing job hunting. You tell it what job you want, give it your CV, and it:

1. Finds real job listings on LinkedIn (via Apify scraper)
2. Scores each job against your actual CV and only keeps the ones you're genuinely a fit for
3. Rewrites your CV slightly to fit each selected job better (never invents skills you don't have)
4. Looks up a real HR/recruiter email for each company (never a guessed/fake address)
5. Writes a personalized email for each job
6. **Stops and waits for you to approve** every email before sending — and blocks approval entirely if the recipient email hasn't been confirmed as real
7. Sends approved emails through your Gmail
8. Records everything with proof (timestamps, hashes)

You are always in control. **No email is ever sent without your approval, and no approval is allowed until the recipient is a confirmed real address.**

---

## THE TWO PARTS

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND (React)          BACKEND (Python/FastAPI)      │
│  http://localhost:5173  ←→  http://localhost:8008        │
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
| `email_drafts`      | AI-written emails waiting for your approval (each carries `recipient_confirmed` — blocks approval until the HR email is a confirmed real address) |
| `application_records` | Permanent record of every email actually sent     |
| `audit_logs`        | Every action the system took (for accountability)   |
| `execution_states`  | Current phase of each workflow step                 |

---

## THE AI BRAIN

The system uses real AI APIs (not a local model):

```
Groq (primary)         →  OpenRouter (fallback)   →  Rule-based logic (last resort)
     ↓                        ↓                        ↓
llama-3.3-70b               llama-3.3-70b:free      Hardcoded templates
(ultra-fast, reliable)      (free tier, rate-limited) (always works, no API)
```

If Groq is busy or fails → tries OpenRouter automatically.
If OpenRouter also fails → uses simple rule-based templates. **The system never crashes due to AI failure.**
(Groq is primary, not OpenRouter, because OpenRouter's free tier gets rate-limited often — Groq's free tier has been more reliable in practice.)

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
**Who does it:** AI (Groq/OpenRouter)

The AI reads your full CV (up to 8000 characters, so nothing near the end like Education/Languages gets cut off) and extracts structured info:
```json
{
  "name": "...", "location": "...", "phone": "...", "email": "...", "linkedin": "...",
  "skills": ["Python", "Django", "SQL", "Docker"],
  "tools": ["Git", "Docker", "AWS"],
  "experience": [{"role": "Backend Dev", "years": 3, "projects": [...]}],
  "key_achievements": [...],
  "education": "BSc Computer Science",
  "languages": ["English", "Urdu"]
}
```
This structured data is used later for job matching and CV optimization.
Saved to `cv_versions` table as the **Master CV**.
If the AI is unreachable, a regex-based fallback still pulls out name/email/phone/linkedin so the profile is never empty.

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

### PHASE 4b — HR Email Discovery
**Who does it:** Backend (waterfall of external lookup services)

For each company, the backend tries real lookups in order until one works: **Anymail Finder → Hunter.io → Snov.io → company-website scrape**. If none succeed, it tries a free domain-guessing fallback — it never invents a "jobs@company.com"-style fake address.

Each job gets an `hr_email_confidence` of `verified`, `likely`, or none. This confidence directly controls whether you can approve the email later (Phase 8) — no confirmed address means no auto-approval.

---

### PHASE 5 — Job Selection (Relevance Matching)
**Who does it:** AI (Groq/OpenRouter) + Backend

The AI scores **every** scraped job against your parsed CV (skills/experience overlap, `score_job_match`), returning a 0-100 match score, matched skills, and missing skills.

The backend sorts jobs by score and selects **up to 5** that clear a 40% relevance bar — never picks jobs at random, and never selects a poor fit just to hit a count. Selected jobs get status = `Selected`; the rest are marked `Matched` (seen, not pursued) along with their real score.

If fewer than 5 jobs clear the bar, the mission proceeds with fewer — it does not lower the bar to force a count.

---

### PHASE 6 — CV Versioning
**Who does it:** AI (Groq/OpenRouter)

For every selected job, the AI creates a **tailored version of your CV** following a fixed professional structure (header + contact info, pitch bullets, Professional Skills, Professional Work Experience, Key Achievements, Education, Languages):
- Adds keywords from the job description
- Reorders bullet points to highlight relevant experience
- Includes Education/Languages when you provided them, omits the section entirely when you didn't (never prints a placeholder like "not provided")
- **Never fabricates — only rearranges/emphasizes what's already there**, even for a job that's only a partial fit

Each version saved to `cv_versions` with a link to the specific job.

---

### PHASE 7 — Email Generation
**Who does it:** AI (Groq/OpenRouter)

For every selected job, the AI writes a **personalized application email** (< 200 words):
- Professional tone
- Mentions the company and role specifically
- Highlights your top matching skills
- Addressed to the HR person if their name was found

Email saved to `email_drafts` with status = `PendingApproval`. `recipient_confirmed` is set true only if Phase 4b found a `verified` or `likely` real HR email.
**The email is NOT sent yet.**

---

### PHASE 8 — Human Approval (HITL)
**Who does it:** YOU

This is the mandatory human checkpoint. The frontend shows you every email draft.

You have 3 choices for each email:
- ✅ **Approve & Send** → email will be sent as-is (only shown/enabled if the recipient is already confirmed real)
- ✏️ **Fix recipient to approve** → shown instead of Approve when the HR email isn't confirmed yet; lets you correct the To: address, then approve
- ❌ **Reject** → skip this job entirely

**Nothing gets sent until you approve it, and you can't approve an email whose recipient hasn't been confirmed as a real address. This is enforced by the system — it's not optional.**

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
    ├── orchestrator.py     ← Master 12-phase workflow controller (job matching, recipient-confirmation gate)
    ├── ai/
    │   ├── llm_service.py  ← Groq → OpenRouter → Rule-based AI (CV parsing, job scoring, CV/email generation)
    │   └── ollama_service.py ← Thin alias to llm_service (backward compat)
    └── mcp/
        ├── apify_service.py  ← Calls Apify API to scrape jobs
        ├── apollo_service.py ← HR email waterfall (Anymail → Hunter → Snov → website scrape → domain guesser)
        └── gmail_service.py  ← Calls Gmail API to send emails
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
| POST   | /api/emails/{id}/approve       | Approve an email (400 if recipient not confirmed) |
| POST   | /api/emails/{id}/reject        | Reject an email                           |
| PATCH  | /api/emails/{id}               | Edit an email draft (content and/or to_email — editing to_email confirms the recipient) |
| POST   | /api/applications/send         | Send an approved application              |
| GET    | /api/applications/             | List all sent applications                |
| POST   | /api/cvversions/extract-pdf    | Extract text from an uploaded PDF resume  |

---

## THE GOVERNANCE RULES (Constitution)

These rules are hardcoded and cannot be bypassed:

1. **No email sent without human approval** — HITL is mandatory (Phase 8)
2. **No approval without a confirmed real recipient** — a guessed/fake HR address blocks the Approve button until you fix it (Phase 8, constitution.md §3.5)
3. **Max 20 applications per day** — enforced before every send (Phase 9)
4. **No fabrication** — AI only rearranges/emphasizes, never invents experience or skills to force a fit with an unrelated job, even if asked to (constitution.md §9.6)
5. **Jobs must clear a relevance bar to be selected** — no random job selection (Phase 5, constitution.md §9.5)
6. **Full audit trail** — every action logged with timestamp
7. **Retry policy** — max 3 attempts, waits 2s/4s/8s between retries
8. **Single job failure doesn't stop the workflow** — it logs and continues

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
- `Scraped` → Found by Apify, not scored/selected yet
- `Matched` → Scored, but below the 40% relevance bar (or not among the top 5) — not pursued
- `Selected` → Scored above the relevance bar and chosen to apply (up to 5, best first)
- `CV_Optimized` → Tailored CV created
- `Email_Drafted` → Email written, waiting approval
- `Approved` → You approved the email
- `Applied` → Email sent successfully
- `Rejected` → You rejected it, or score too low
- `Failed` → Send failed after 3 retries

**Email status:**
- `PendingApproval` → Waiting for you to review (check `recipient_confirmed` — if false, Approve is blocked until you fix the recipient)
- `Approved` → You approved it
- `Rejected` → You rejected it
- `Sent` → Successfully delivered via Gmail

---

*Last updated: 2026-07-16 — Groq/OpenRouter order corrected, relevance-based job matching, HR email confidence + recipient-confirmation gate, education/languages CV parsing, PDF upload extraction, backend port corrected to 8008*
