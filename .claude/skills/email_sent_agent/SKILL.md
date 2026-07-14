---
name: email_sender
description: Sends email using MCP-connected email service.
version: 1.0
token_budget: low
recommended_model: claude
---

# PURPOSE

Send generated email via Gmail MCP.

---

# RESPONSIBILITIES

- Validate recipient
- Attach resume
- Call MCP
- Log status

---

# RULES

- Do not generate email content
- Only send validated content
- Handle retry logic