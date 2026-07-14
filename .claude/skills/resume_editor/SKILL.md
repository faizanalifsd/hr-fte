
name: resume_editing
description: Professional resume editor that transforms raw or rough resumes into polished, email-ready documents. Use this skill whenever the user wants to edit, improve, rewrite, polish, or send a resume — including when they mention "fixing my resume", "cleaning up my CV", "making my resume better", "sending my resume to someone", "resume for a job application", or any variation. Also triggers for cover letter pairing and resume-to-email formatting. Always use this skill when a resume is involved, even if the user only says "can you make this sound more professional?"
version: 3.0
token_budget: medium
---

# PURPOSE

Transform a resume into a polished, professional document ready to be shared via email with recruiters, hiring managers, or connections. When tailoring for a specific job, actively rewrite skills and experience to match the role — while keeping all facts truthful. The final CV must be completely undetectable as AI-generated.

---

# WORKFLOW

## Step 1 — Understand Context
Before editing, check if the user has shared:
- **Target role or industry** (tailor tone and keywords accordingly)
- **Who it's being sent to** (recruiter, direct manager, cold outreach, referral)
- **Resume content** (paste, upload, or describe)

If missing, ask only the most important question: *"What role or type of job is this resume for?"*

---

## Step 2 — Tailor the Resume to the Job

When a target job is provided, do NOT just rearrange — actively rewrite:

### Job Adaptation Rules
- **Reframe experience bullets** using the job description's exact vocabulary and terminology
- **Adapt skills** — reorder to put most relevant skills first; rephrase generic skills to match the job's specific tools/stack
- **Rewrite the Summary** as a direct pitch for this exact role — mention the job title naturally
- **Mirror the job's language** — if the job says "cross-functional collaboration", use that phrase; if it says "stakeholder management", use that
- **Emphasize overlapping achievements** — if a past role had anything touching the job's domain, bring it forward and expand it
- Every bullet should make a hiring manager think: "this person has done exactly this before"

---

## Step 3 — Make It Undetectable as AI-Generated

This is critical. Apply ALL of the following:

### Anti-AI Language Rules
- **Never use these AI-tell words/phrases:**
  - "Leverage / Leveraged / Leveraging"
  - "Additionally", "Furthermore", "Moreover", "In conclusion"
  - "It's worth noting", "Notably", "Certainly", "Absolutely"
  - "Spearheaded" (overused), "Synergy", "Utilize/Utilized"
  - "Demonstrated expertise", "Proven track record", "Results-driven professional"
  - "Passionate about", "Dedicated to", "Committed to"
  - Any phrase starting with "As a [role],"

### Natural Human Variation Rules
- **Mix bullet lengths** — some bullets 1 line, some 2 lines; never all the same length
- **Vary sentence openers** — not every bullet should start with an action verb; occasionally start with a tool, context, or outcome:
  - Bad (AI): "Led, Built, Developed, Managed, Implemented" — all the same structure
  - Good (human): mix of "Built...", "Reduced X by Y...", "Worked with [team] to...", "Full ownership of..."
- **Use contractions and casual specificity** in the Summary only (e.g. "5 years in", "day-to-day", "hands-on")
- **Include one or two slightly informal but honest phrases** — this is what humans do; AI never does this
- **Vary punctuation style** — some bullets end with a period, some don't; mix dashes and colons naturally
- **Use numbers and specifics wherever possible** — even rough ones ("~30%", "3-person team", "across 4 departments")
- **Do NOT make every experience bullet perfectly parallel** — real humans don't write like that
- **Avoid superlatives** — "best", "top-tier", "world-class" sound fabricated

### Structure (in order)
1. **Name + Contact Info** — clean header (name, email, phone, LinkedIn/portfolio if relevant)
2. **Professional Summary** — 2–3 sentences. Conversational but sharp. Reads like a real person wrote it
3. **Skills** — concise, scannable; reordered and rephrased to match the job
4. **Experience** — reverse chronological; company, title, dates, 3–5 bullets per role (varied length and structure)
5. **Projects** *(if applicable)* — name, 1-line description, outcomes
6. **Education** — degree, institution, year

### Integrity Rules
- Never invent metrics, achievements, or titles
- Never change job dates
- If a bullet is vague, sharpen the language — don't fabricate specifics
- If something seems like an error, flag it with a note rather than silently changing it
- Reframe what's real — never add what isn't

---

## Step 4 — Deliver the Output

Provide two things:

### A. The Polished Resume
Format in clean Markdown, ready to copy into an email or document.

### B. Email Draft to Send It
Write a short, professional email the user can send with their resume attached. Tailor based on:
- **Cold outreach** → concise, confident, clear ask
- **Referral** → warmer tone, mention the connection
- **Job application** → aligned to the role, expresses interest

**Email format:**
```
Subject: [Name] — [Role/Purpose]

Hi [Name / Hiring Team],

[2–3 sentences: who you are, why you're reaching out, what you're attaching]

[1 sentence: what you're looking for / the ask]

Best regards,
[Full Name]
[Phone] | [Email] | [LinkedIn]
```

---

## Step 5 — Flag Issues (if any)

If you notice problems, list them briefly after the output:
- Unexplained employment gaps
- Vague bullets that need real data from the user
- Missing sections (e.g., no contact info)
- Possible errors in dates or titles

Format as: `⚠️ [Issue]: [What to check or add]`

---

# OUTPUT EXAMPLE STRUCTURE

```
# Jane Doe
jane@email.com | 555-123-4567 | linkedin.com/in/janedoe

## Summary
Marketing manager with 6 years in B2B growth, mostly in SaaS. Day-to-day focus has been
demand gen and lifecycle email — currently looking for a senior IC role where I can own
the full funnel.

## Skills
HubSpot · Salesforce · Google Analytics · SQL · A/B Testing · Marketo · Segment

## Experience
**Senior Marketing Manager — Acme Corp | 2021–Present**
- Rebuilt the email nurture sequence from scratch; open rates went from 18% to 34% over 6 months
- Budget ownership: ~$500K/year across paid, content, and events
- Worked closely with Sales (7-person team) to align on ICP and shorten the sales cycle

**Marketing Manager — BetaCo | 2018–2021**
- Ran all demand gen for a 3-product portfolio — no dedicated team, fully self-managed
- Cut cost-per-lead by 22% by moving spend from trade shows to targeted LinkedIn campaigns

## Education
B.S. Marketing — University of Texas | 2017
```

---EMAIL DRAFT---

Subject: Jane Doe — Senior Marketing Role

Hi [Hiring Manager],

I'm a marketing manager with 6 years of hands-on demand gen experience, mostly in SaaS.
Came across the role and it lines up closely with what I've been doing at Acme — full-funnel
ownership, cross-functional alignment with Sales, and a heavy focus on lifecycle email.

Attaching my resume — happy to chat if there's a fit.

Best regards,
Jane Doe
555-123-4567 | jane@email.com | linkedin.com/in/janedoe
```
