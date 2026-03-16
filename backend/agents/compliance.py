"""
CampaignX — Compliance Agent.

BFSI brand-safety checks for email content:
  • English-only text verification
  • URL validation (exactly one: https://superbfsi.com/xdeposit/explore/)
  • No misleading financial claims
  • No prohibited language
"""

import re
from typing import Any, Dict, List

from agents.state import CampaignState


# ─── Constants ────────────────────────────────────────────────────────────────

REQUIRED_URL = "https://superbfsi.com/xdeposit/explore/"

# Prohibited phrases for BFSI compliance
PROHIBITED_PHRASES = [
    "guaranteed returns",
    "risk-free",
    "no risk",
    "100% safe",
    "double your money",
    "get rich quick",
    "unlimited returns",
    "zero risk",
    "assured returns",
    "guaranteed profit",
    "no loss",
    "certain profit",
    "fixed guaranteed",
]

# Regex to detect non-English characters (allows ASCII, common punctuation, emojis, HTML)
NON_ENGLISH_PATTERN = re.compile(
    r"[^\x00-\x7F"
    r"\U0001F300-\U0001F9FF"   # Emojis block 1
    r"\U00002702-\U000027B0"   # Dingbats
    r"\U0000FE00-\U0000FE0F"   # Variation selectors
    r"\U0001FA00-\U0001FA6F"   # Chess symbols & extended-A
    r"\U0001FA70-\U0001FAFF"   # Symbols & pictographs extended-A
    r"\U00002600-\U000026FF"   # Misc symbols
    r"\U0000200D"              # Zero-width joiner
    r"]"
)

# URLs pattern
URL_PATTERN = re.compile(r'https?://[^\s<>"\']+')


# ─── Validation Functions ────────────────────────────────────────────────────


def _check_english_only(text: str, field_name: str) -> List[str]:
    """Check that text contains only English characters (+ emojis for body)."""
    issues = []
    # Strip HTML tags for content analysis
    stripped = re.sub(r"<[^>]+>", "", text)

    matches = NON_ENGLISH_PATTERN.findall(stripped)
    if matches:
        sample = "".join(matches[:5])
        issues.append(
            f"{field_name} contains non-English characters: '{sample}'. "
            f"Only English text{' and emojis' if field_name == 'Body' else ''} allowed."
        )
    return issues


def _check_subject_constraints(subject: str) -> List[str]:
    """Subject must be English-only, no URLs, no HTML."""
    issues = []

    if not subject or not subject.strip():
        issues.append("Subject is empty.")
        return issues

    # No HTML tags in subject
    if re.search(r"<[^>]+>", subject):
        issues.append("Subject must not contain HTML tags.")

    # No URLs in subject
    if URL_PATTERN.search(subject):
        issues.append("Subject must not contain URLs.")

    # Length check
    if len(subject) > 80:
        issues.append(f"Subject is too long ({len(subject)} chars). Recommended: under 60 chars.")

    # English only (no emojis in subject to keep it clean)
    non_ascii = [c for c in subject if ord(c) > 127]
    if non_ascii:
        issues.append(
            f"Subject must contain ONLY English text. "
            f"Found non-ASCII characters: {''.join(non_ascii[:5])}"
        )

    return issues


def _check_body_constraints(body: str) -> List[str]:
    """Body must have exactly one URL, English + emojis, and HTML formatting."""
    issues = []

    if not body or not body.strip():
        issues.append("Body is empty.")
        return issues

    # ── URL validation ──
    # Strip HTML attributes to find URLs in text and href attributes
    urls_found = URL_PATTERN.findall(body)
    # Normalize URLs (remove trailing punctuation)
    clean_urls = set()
    for url in urls_found:
        url = url.rstrip(".,;:!?'\")")
        clean_urls.add(url)

    if REQUIRED_URL not in clean_urls and REQUIRED_URL.rstrip("/") not in clean_urls:
        issues.append(
            f"Body MUST contain the required URL: {REQUIRED_URL}"
        )

    disallowed_urls = {u for u in clean_urls if u != REQUIRED_URL and u != REQUIRED_URL.rstrip("/")}
    if disallowed_urls:
        issues.append(
            f"Body contains unauthorized URLs: {', '.join(list(disallowed_urls)[:3])}. "
            f"Only {REQUIRED_URL} is allowed."
        )

    # ── English + emoji check ──
    issues.extend(_check_english_only(body, "Body"))

    # ── HTML formatting check (informational, not blocking) ──
    has_bold = "<b>" in body.lower() or "<strong>" in body.lower()
    has_italic = "<i>" in body.lower() or "<em>" in body.lower()
    has_underline = "<u>" in body.lower()

    if not (has_bold or has_italic or has_underline):
        issues.append(
            "Body should use HTML font variations: <b>bold</b>, <i>italic</i>, <u>underline</u>."
        )

    return issues


def _check_prohibited_language(text: str) -> List[str]:
    """Check for misleading financial claims."""
    issues = []
    lower_text = text.lower()

    for phrase in PROHIBITED_PHRASES:
        if phrase in lower_text:
            issues.append(
                f"Prohibited BFSI language detected: \"{phrase}\". "
                f"Remove misleading financial claims."
            )

    return issues


# ─── Agent Node ───────────────────────────────────────────────────────────────


def compliance_node(state: CampaignState) -> Dict[str, Any]:
    """
    LangGraph node: Validate email content for BFSI brand safety.

    Reads:  state["email_subject"], state["email_body"]
    Writes: state["compliance_approved"], state["compliance_issues"],
            state["compliance_retries"], state["logs"], state["status"]
    """
    subject = state.get("email_subject", "")
    body = state.get("email_body", "")
    logs = list(state.get("logs", []))
    retries = state.get("compliance_retries", 0)

    logs.append({
        "agent": "compliance",
        "action": "validating_content",
        "detail": f"Checking subject + body for BFSI brand safety (attempt {retries + 1}).",
    })

    all_issues: List[str] = []

    # Run all checks
    all_issues.extend(_check_subject_constraints(subject))
    all_issues.extend(_check_body_constraints(body))
    all_issues.extend(_check_prohibited_language(subject + " " + body))

    approved = len(all_issues) == 0

    if approved:
        logs.append({
            "agent": "compliance",
            "action": "approved",
            "detail": "Content passed all BFSI compliance checks. ✅",
        })
        
        disclaimer = "<p><small><i>*Disclaimer: SuperBFSI interest rates are subject to market risks. Read all scheme related documents carefully.</i></small></p>"
        if disclaimer not in state.get("email_body", ""):
            state["email_body"] = state.get("email_body", "") + f"\n\n{disclaimer}"
            
    else:
        logs.append({
            "agent": "compliance",
            "action": "rejected",
            "detail": f"Content has {len(all_issues)} issue(s): {'; '.join(all_issues[:3])}",
        })

    return {
        "email_body": state.get("email_body", ""),
        "compliance_approved": approved,
        "compliance_issues": all_issues,
        "compliance_retries": retries + 1,
        "logs": logs,
        "status": "compliance_passed" if approved else "compliance_failed",
    }
