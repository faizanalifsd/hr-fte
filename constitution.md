# DIGITAL FTE CONSTITUTION
Version: 1.0
System: Mission-Driven Autonomous Job Application Agent
Owner: Faizan Ali

---

## 1. CORE IDENTITY

The system operates as a Mission-Driven Digital FTE (Full-Time Employee).

It does not function as a simple automation script.
It executes delegated objectives autonomously under defined governance rules.

All behavior must align with:
- Goal completion
- Ethical automation
- Security compliance
- Audit traceability

---

## 2. MISSION GOVERNANCE

2.1 A mission must exist before execution begins.

2.2 A mission must contain:
- Target role
- Target application count
- Optional time constraint

2.3 Mission status states:
- Initialized
- Running
- Paused
- Completed
- Failed

2.4 A mission is only marked Completed when:
- Target count achieved
- All applications logged successfully

---

## 3. HUMAN-IN-THE-LOOP (HITL)

3.1 No email may be sent without explicit human approval.

3.2 Approval must occur after:
- CV optimization
- Email generation

3.3 User must be able to:
- Approve
- Edit
- Reject

3.4 Rejected items must be logged.

---

## 4. ERROR HANDLING POLICY

4.1 All agent failures must trigger:
- Automatic retry (max 3 attempts)
- Exponential backoff

4.2 If retry fails:
- Mark step as Failed
- Log error
- Notify user

4.3 External dependency failures (Apify, Gmail API):
- Trigger fallback logic
- Pause mission if critical failure

4.4 Zero job results:
- Notify user
- Suggest broader search
- Do not crash pipeline

---

## 5. SECURITY POLICY

5.1 All OAuth tokens must be encrypted at rest.

5.2 No credentials may be stored in plain text.

5.3 Role-based access control must restrict:
- Mission execution
- Email sending

5.4 Rate limiting:
- Max 20 applications per day (default)
- Configurable but capped

5.5 Sensitive data:
- CV data encrypted
- No third-party sharing without consent

---

## 6. AUDIT & LOGGING

6.1 Every mission must generate immutable logs.

Each log entry must contain:
- Timestamp
- Agent name
- Input reference
- Output summary
- Status (Success / Failed)

6.2 Application logs must store:
- Company
- HR email
- Timestamp
- Email content hash

6.3 Logs must be queryable by mission ID.

6.4 System must support reproducibility of mission history.

---

## 7. DATA MODEL ENFORCEMENT

Required Entities:

- Mission
- Job
- CVVersion
- EmailDraft
- ApplicationRecord
- ExecutionState
- AuditLog

All relationships must be properly structured.
No implicit or untracked state transitions allowed.

---

## 8. SCALABILITY RULES

8.1 Large missions (50+ applications):
- Must use task queue
- Must process in batches

8.2 Gmail rate limits must be respected.

8.3 Concurrency must not exceed safe API thresholds.

---

## 9. ETHICAL AUTOMATION POLICY

9.1 No spam behavior allowed.

9.2 Applications must:
- Be personalized
- Match job description

9.3 System must enforce:
- Daily application cap
- HITL approval

9.4 User must retain final authority.

---

## 10. RUNTIME EXECUTION VISIBILITY

10.1 Execution state must be trackable.

States:
- Idle
- Running
- Completed
- Failed

10.2 Graph view must reflect real-time execution state.

---

## 11. FAILURE CONTAINMENT

11.1 Failure in one job branch must not crash entire mission.

11.2 Failed branches must:
- Be logged
- Be retryable manually

---

## 12. EXTENSIBILITY

All agents must be modular.

New agents must:
- Follow logging rules
- Follow retry policy
- Respect mission governance

---

END OF CONSTITUTION