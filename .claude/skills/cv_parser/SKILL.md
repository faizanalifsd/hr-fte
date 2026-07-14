---
name: cv_parser
description: Extracts structured data from resume text into JSON format.
version: 1.0
token_budget: low
recommended_model: gemini-pro
---

# PURPOSE

Convert raw resume into structured JSON.

---

# OUTPUT FORMAT

{
  "summary": "",
  "skills": [],
  "experience": [],
  "projects": [],
  "education": []
}

---

# RULES

- Do not invent data
- Preserve original facts
- Clean formatting only
- No rewriting content