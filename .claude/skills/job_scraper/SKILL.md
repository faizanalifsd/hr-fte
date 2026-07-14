---
name: job_scraper
description: Extracts job listings using MCP-connected scraping tools.
version: 1.0
token_budget: low
recommended_model: gemini-pro
---

# PURPOSE

Extract structured job data from job portals.

---

# EXPECTED OUTPUT

[
  {
    "company": "",
    "role": "",
    "location": "",
    "requirements": [],
    "apply_link": ""
  }
]

---

# RULES

- Only structure data
- Do not summarize heavily
- Do not hallucinate missing fields