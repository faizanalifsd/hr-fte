"""
HR Email Finder Service — 4-Level Waterfall
============================================
Phase 4B/4C — Finds real HR emails for selected jobs.

Waterfall (best → fallback):
  Level 1 → Anymail Finder  (77.5% find rate, 90 free/month, pay-per-verified)
  Level 2 → Hunter.io       (37.6% find rate, 25 free/month)
  Level 3 → Snov.io         (150 free credits/month)
  Level 4 → Website Scrape  (free, unlimited — scrapes /contact, /careers pages)

Environment variables (.env):
  ANYMAIL_FINDER_API_KEY=...   # https://anymailfinder.com
  HUNTER_API_KEY=...           # https://hunter.io
  SNOV_CLIENT_ID=...           # https://snov.io
  SNOV_CLIENT_SECRET=...
"""

import os
import re
import time
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── API credentials ────────────────────────────────────────────
ANYMAIL_API_KEY    = os.getenv("ANYMAIL_FINDER_API_KEY")
HUNTER_API_KEY     = os.getenv("HUNTER_API_KEY")
SNOV_CLIENT_ID     = os.getenv("SNOV_CLIENT_ID")
SNOV_CLIENT_SECRET = os.getenv("SNOV_CLIENT_SECRET")

# ── HR role keywords (ranked by priority) ─────────────────────
HR_ROLES = [
    "hr", "human resources", "recruiter", "recruiting", "talent acquisition",
    "talent", "people", "hiring", "careers", "staffing", "workforce",
]

# HR-prefixed local-parts, used to rank bare email addresses when no
# position/title metadata is available (e.g. Snov's v2 domain-emails endpoint).
_HR_LOCALS = ["hr", "careers", "recruit", "hiring", "talent", "jobs", "people"]

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_FAKE_TLDS = {
    "png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "css", "js",
    "jsx", "ts", "tsx", "json", "xml", "pdf", "zip", "mp4", "mp3",
}

_SKIP_LOCALS = {
    "noreply", "no-reply", "donotreply", "example", "test",
    "webmaster", "postmaster", "mailer-daemon",
}

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ─────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────

def _is_valid_email(email: str) -> bool:
    if "@" not in email:
        return False
    local, domain = email.rsplit("@", 1)
    parts = domain.split(".")
    if len(parts) < 2 or parts[-1].lower() in _FAKE_TLDS:
        return False
    if local.lower() in _SKIP_LOCALS:
        return False
    return len(local) >= 2


def _build_contact(
    email: str,
    name: Optional[str] = None,
    title: Optional[str] = None,
    linkedin: Optional[str] = None,
    source: Optional[str] = None,
    confidence: str = "likely",
) -> dict:
    return {
        "email":      email.lower().strip("."),
        "name":       name or None,
        "title":      title or None,
        "linkedin":   linkedin or None,
        "source":     source,
        "confidence": confidence,
    }


def _hr_score(title: str) -> int:
    """Score a job title by HR relevance (higher = better)."""
    t = (title or "").lower()
    for i, role in enumerate(HR_ROLES):
        if role in t:
            return len(HR_ROLES) - i
    return 0


# ─────────────────────────────────────────────────────────────
# DOMAIN RESOLVER — uses Hunter company search (free quota)
# ─────────────────────────────────────────────────────────────

def _resolve_domain(company_name: str) -> Optional[str]:
    """Ask Hunter.io to find the domain for a company name."""
    if not HUNTER_API_KEY or not company_name:
        return None
    try:
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"company": company_name, "api_key": HUNTER_API_KEY, "limit": 1},
            timeout=10,
        )
        if resp.status_code == 200:
            domain = resp.json().get("data", {}).get("domain")
            if domain:
                logger.info(f"[DomainResolve] '{company_name}' → {domain}")
                return domain
    except Exception as e:
        logger.warning(f"[DomainResolve] Error: {e}")
    return None


# ─────────────────────────────────────────────────────────────
# DOMAIN GUESSER — free, keyless fallback when Hunter can't resolve
# (no key, quota exhausted, or company not in its index)
# ─────────────────────────────────────────────────────────────

# Legal-entity / job-board noise words stripped from the END of a company
# name only, one at a time, to progressively surface the likely brand name.
# Multi-word entries must come before their single-word components.
_COMPANY_SUFFIXES = [
    "pvt ltd", "pvt. ltd.", "private limited", "pte ltd",
    "careers", "recruitment", "hiring",
    "limited", "ltd", "llc", "llp", "inc", "incorporated",
    "corporation", "corp", "company", "co",
    "holdings", "group", "technologies", "technology",
    "solutions", "systems", "international", "enterprises",
]


def _company_name_candidates(company_name: str) -> List[str]:
    """Progressively strip trailing suffix words, most-stripped candidate first."""
    name = re.sub(r"[^\w\s&-]", "", company_name or "").strip()
    words = name.split()
    candidates: List[str] = []

    while words:
        candidate = " ".join(words)
        if candidate and candidate not in candidates:
            candidates.append(candidate)

        two_word = " ".join(words[-2:]).lower() if len(words) >= 2 else ""
        one_word = words[-1].lower().strip(".")

        if two_word in _COMPANY_SUFFIXES:
            words = words[:-2]
        elif one_word in _COMPANY_SUFFIXES:
            words = words[:-1]
        else:
            break

    # Most-stripped (shortest / likely core brand) first
    return list(reversed(candidates))


def _domain_reachable(domain: str) -> bool:
    """True if the domain resolves and responds to HTTP at all (any status)."""
    try:
        requests.head(f"https://{domain}", headers=_BROWSER_HEADERS, timeout=5, allow_redirects=True)
        return True
    except Exception:
        return False


def _guess_domain(company_name: str) -> Optional[str]:
    """
    Free, keyless domain guesser: strips legal/job-board suffixes off the
    company name, slugifies what's left, and verifies candidates against
    common TLDs with a live HTTP check. Best-effort — only used when Hunter's
    domain-search isn't available or didn't find anything.
    """
    if not company_name:
        return None

    for candidate in _company_name_candidates(company_name):
        slug = re.sub(r"[^a-z0-9]", "", candidate.lower())
        if not slug:
            continue
        for tld in ("com", "co", "io"):
            domain = f"{slug}.{tld}"
            if _domain_reachable(domain):
                logger.info(f"[DomainGuess] '{company_name}' → {domain} (via '{candidate}')")
                return domain

    logger.info(f"[DomainGuess] No reachable domain guessed for '{company_name}'")
    return None


# ─────────────────────────────────────────────────────────────
# LEVEL 1 — Anymail Finder
# ─────────────────────────────────────────────────────────────

def _find_via_anymail(company_name: str, domain: Optional[str]) -> Optional[dict]:
    if not ANYMAIL_API_KEY:
        logger.debug("[Anymail] API key not set — skipping")
        return None

    logger.info(f"[Anymail] Searching HR contact for '{company_name}'...")

    # Decision-maker endpoint (targets HR department specifically)
    try:
        resp = requests.post(
            "https://api.anymailfinder.com/v5.1/find-email/decision-maker",
            json={"company_name": company_name, "category": "hr"},
            headers={
                "Authorization": f"Bearer {ANYMAIL_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            email = data.get("email") or (data.get("result") or {}).get("email")
            if email and _is_valid_email(email):
                logger.info(f"[Anymail] ✅ decision-maker: {email}")
                return _build_contact(
                    email=email,
                    name=data.get("full_name"),
                    title=data.get("title"),
                    source="anymail_decision_maker",
                    confidence="verified" if data.get("result_type") == "email" else "likely",
                )
        elif resp.status_code == 402:
            logger.warning("[Anymail] Credit limit reached")
            return None
    except Exception as e:
        logger.warning(f"[Anymail] Decision-maker error: {e}")

    # Domain search fallback
    if domain:
        try:
            resp = requests.post(
                "https://api.anymailfinder.com/v5.1/find-email/domain",
                json={"domain": domain},
                headers={
                    "Authorization": f"Bearer {ANYMAIL_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                email = data.get("email") or (data.get("result") or {}).get("email")
                if email and _is_valid_email(email):
                    logger.info(f"[Anymail] ✅ domain search: {email}")
                    return _build_contact(
                        email=email,
                        name=data.get("full_name"),
                        title=data.get("title"),
                        source="anymail_domain",
                        confidence="likely",
                    )
        except Exception as e:
            logger.warning(f"[Anymail] Domain search error: {e}")

    return None


# ─────────────────────────────────────────────────────────────
# LEVEL 2 — Hunter.io
# ─────────────────────────────────────────────────────────────

def _find_via_hunter(company_name: str, domain: Optional[str]) -> Optional[dict]:
    if not HUNTER_API_KEY:
        logger.debug("[Hunter] API key not set — skipping")
        return None
    if not domain:
        logger.debug("[Hunter] No domain — skipping")
        return None

    logger.info(f"[Hunter] Domain search for '{domain}'...")

    try:
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={
                "domain":  domain,
                "api_key": HUNTER_API_KEY,
                "limit":   10,
                "type":    "personal",
            },
            timeout=15,
        )
        resp.raise_for_status()
        emails_list = resp.json().get("data", {}).get("emails", [])

        if not emails_list:
            logger.info("[Hunter] No emails found")
            return None

        ranked = sorted(
            emails_list,
            key=lambda e: (
                _hr_score(e.get("position") or e.get("type") or ""),
                1 if (e.get("verification") or {}).get("status") == "valid" else 0,
                e.get("confidence", 0),
            ),
            reverse=True,
        )

        for entry in ranked:
            email = entry.get("value")
            if email and _is_valid_email(email):
                name = f"{entry.get('first_name', '')} {entry.get('last_name', '')}".strip() or None
                logger.info(f"[Hunter] ✅ {email} ({entry.get('position', '?')})")
                verified = (entry.get("verification") or {}).get("status") == "valid"
                return _build_contact(
                    email=email,
                    name=name,
                    title=entry.get("position"),
                    linkedin=entry.get("linkedin"),
                    source="hunter_domain_search",
                    confidence="verified" if verified else "likely",
                )

    except requests.HTTPError as e:
        if e.response.status_code == 429:
            logger.warning("[Hunter] Monthly quota exhausted")
        else:
            logger.error(f"[Hunter] HTTP error: {e}")
    except Exception as e:
        logger.error(f"[Hunter] Search error: {e}")

    return None


# ─────────────────────────────────────────────────────────────
# LEVEL 3 — Snov.io
# ─────────────────────────────────────────────────────────────

def _get_snov_token() -> Optional[str]:
    try:
        resp = requests.post(
            "https://api.snov.io/v1/oauth/access_token",
            json={
                "grant_type":    "client_credentials",
                "client_id":     SNOV_CLIENT_ID,
                "client_secret": SNOV_CLIENT_SECRET,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        logger.error(f"[Snov] Token error: {e}")
        return None


def _find_via_snov(company_name: str, domain: Optional[str]) -> Optional[dict]:
    """
    Uses Snov's v2 async domain-emails search:
      POST /v2/domain-search/domain-emails/start  → {meta: {task_hash}}
      GET  /v2/domain-search/domain-emails/result/{task_hash} → polled until status == "completed"

    Note: v2 only returns bare email addresses (no name/position/verification),
    unlike the deprecated v1 /get-domain-emails endpoint this replaced. Results
    are therefore ranked by HR-prefixed local-part and marked "likely" (unverified).
    """
    if not SNOV_CLIENT_ID or not SNOV_CLIENT_SECRET:
        logger.debug("[Snov] Credentials not set — skipping")
        return None
    if not domain:
        logger.debug("[Snov] No domain — skipping")
        return None

    logger.info(f"[Snov] Domain search for '{domain}'...")

    token = _get_snov_token()
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = requests.post(
            "https://api.snov.io/v2/domain-search/domain-emails/start",
            json={"domain": domain},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        task_hash = resp.json().get("meta", {}).get("task_hash")
        if not task_hash:
            logger.info("[Snov] No task_hash returned")
            return None

        result_url = f"https://api.snov.io/v2/domain-search/domain-emails/result/{task_hash}"

        emails_list = []
        for _ in range(6):
            time.sleep(1.5)
            poll_resp = requests.get(result_url, headers=headers, timeout=15)
            poll_resp.raise_for_status()
            poll_data = poll_resp.json()
            if poll_data.get("status") == "completed":
                emails_list = poll_data.get("data", [])
                break
        else:
            logger.info("[Snov] Timed out waiting for domain search result")
            return None

        if not emails_list:
            logger.info("[Snov] No emails found")
            return None

        ranked = sorted(
            emails_list,
            key=lambda e: next(
                (len(_HR_LOCALS) - i for i, p in enumerate(_HR_LOCALS) if (e.get("email") or "").lower().startswith(p)),
                -1,
            ),
            reverse=True,
        )

        for entry in ranked:
            email = entry.get("email")
            if email and _is_valid_email(email):
                logger.info(f"[Snov] ✅ {email}")
                return _build_contact(
                    email=email,
                    source="snov_domain_search",
                    confidence="likely",  # v2 endpoint returns unverified emails
                )

    except requests.HTTPError as e:
        if e.response.status_code == 429:
            logger.warning("[Snov] Rate limit hit")
        else:
            logger.error(f"[Snov] HTTP error: {e}")
    except Exception as e:
        logger.error(f"[Snov] Search error: {e}")

    return None


# ─────────────────────────────────────────────────────────────
# LEVEL 4 — Website Scrape (free fallback)
# ─────────────────────────────────────────────────────────────

def _find_via_website_scrape(domain: Optional[str]) -> Optional[dict]:
    if not domain:
        return None

    logger.info(f"[Scrape] Scanning '{domain}' for emails...")

    pages = [
        f"https://{domain}",
        f"https://{domain}/contact",
        f"https://{domain}/careers",
    ]

    for url in pages:
        try:
            resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=5, allow_redirects=True)
            if resp.status_code != 200:
                continue

            found = [
                e.lower().strip(".,;")
                for e in _EMAIL_RE.findall(resp.text)
                if _is_valid_email(e)
                and domain.split(".")[0] in e.lower()
            ]

            if not found:
                continue

            # Prioritise HR-prefixed emails
            hr_first = sorted(
                found,
                key=lambda e: next(
                    (len(_HR_LOCALS) - i for i, p in enumerate(_HR_LOCALS) if e.startswith(p)),
                    -1,
                ),
                reverse=True,
            )

            email = hr_first[0]
            logger.info(f"[Scrape] ✅ Found {email} on {url}")
            return _build_contact(
                email=email,
                source="website_scrape",
                confidence="likely",
            )

        except Exception:
            continue

    logger.info("[Scrape] No emails found on website")
    return None


# ─────────────────────────────────────────────────────────────
# MASTER WATERFALL
# ─────────────────────────────────────────────────────────────

def find_hr_email(company_name: str, company_domain: Optional[str] = None) -> dict:
    """
    Tries all 4 levels in order. Returns on first success.

    Returns dict with keys:
        email, name, title, linkedin, source, confidence, found
    """
    empty = {
        "email": None, "name": None, "title": None,
        "linkedin": None, "source": None, "confidence": "none", "found": False,
    }

    if not company_name:
        return empty

    domain = company_domain
    if not domain:
        domain = _resolve_domain(company_name)
    if not domain:
        domain = _guess_domain(company_name)

    logger.info(f"[Waterfall] '{company_name}' | domain={domain}")

    for level, fn in [
        ("Anymail", lambda: _find_via_anymail(company_name, domain)),
        ("Hunter",  lambda: _find_via_hunter(company_name, domain)),
        ("Snov",    lambda: _find_via_snov(company_name, domain)),
        ("Scrape",  lambda: _find_via_website_scrape(domain)),
    ]:
        try:
            result = fn()
            if result and result.get("email"):
                logger.info(f"[Waterfall] ✅ Found via {level}: {result['email']}")
                return {**result, "found": True}
        except Exception as e:
            logger.warning(f"[Waterfall] {level} raised: {e}")
        time.sleep(0.3)

    logger.info(f"[Waterfall] No email found for '{company_name}'")
    return empty


# ─────────────────────────────────────────────────────────────
# PER-JOB RESOLVER (called in parallel by batch processor)
# ─────────────────────────────────────────────────────────────

def resolve_hr_contact(job: dict) -> dict:
    """
    Runs the full waterfall for a single job dict.
    Maps result fields to DB column names (hr_email_confidence etc.).
    """
    company_name = job.get("company", "")
    apply_link   = job.get("apply_link", "") or ""

    # Try to extract domain from apply_link if available
    domain = None
    if apply_link:
        parsed = urlparse(apply_link)
        host = parsed.netloc.lower().replace("www.", "")
        # Skip job board domains
        if host and not any(
            board in host for board in ["indeed.com", "linkedin.com", "rozee.pk", "glassdoor.com"]
        ):
            domain = host

    contact = find_hr_email(company_name, domain)

    return {
        **job,
        "company":             company_name,
        "hr_email":            contact.get("email") or job.get("hr_email"),
        "hr_name":             contact.get("name") or job.get("hr_name"),
        "hr_title":            contact.get("title") or "HR / Recruiter",
        "hr_email_confidence": contact.get("confidence", "none"),
        "email_lookup_status": "found" if contact.get("found") else "not_found",
    }


# ─────────────────────────────────────────────────────────────
# BATCH PROCESSOR — parallel execution
# ─────────────────────────────────────────────────────────────

def _safe_resolve(index: int, job: dict) -> tuple:
    logger.info(f"[Batch] ── Job {index + 1} ({job.get('company', '?')}) ──")
    try:
        return index, resolve_hr_contact(job)
    except Exception as e:
        logger.error(f"[Batch] Failed for '{job.get('company')}': {e}")
        return index, {
            **job,
            "hr_email":            job.get("hr_email"),
            "hr_name":             job.get("hr_name"),
            "hr_title":            "HR / Recruiter",
            "hr_email_confidence": "none",
            "email_lookup_status": "error",
        }


def enrich_jobs_with_hr_emails(jobs: list) -> list:
    """
    Enriches each job with a real HR email via the 4-level waterfall.
    Runs all jobs in parallel. Never blocks the pipeline.
    """
    enriched = [None] * len(jobs)

    with ThreadPoolExecutor(max_workers=min(5, len(jobs))) as executor:
        futures = {executor.submit(_safe_resolve, i, job): i for i, job in enumerate(jobs)}
        for future in as_completed(futures):
            idx, result = future.result()
            enriched[idx] = result

    found = sum(1 for j in enriched if j and j.get("email_lookup_status") == "found")
    logger.info(f"[Batch] Complete: {found}/{len(jobs)} HR emails found")
    return enriched
