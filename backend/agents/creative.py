"""
CampaignX — Creative Agent.

Generates email content with STRICT constraints:
  • Subject: English text only
  • Body: English text + emojis + exactly ONE URL
  • HTML font variations: <b>, <i>, <u>
  • URL must be exactly: https://superbfsi.com/xdeposit/explore/
"""

import json
import os
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.state import CampaignState


# ─── Constants ────────────────────────────────────────────────────────────────

REQUIRED_URL = "https://superbfsi.com/xdeposit/explore/"


# ─── System Prompt ────────────────────────────────────────────────────────────

CREATIVE_SYSTEM_PROMPT = f"""You are the Creative Agent for SuperBFSI email marketing campaigns.

Your job is to generate compelling email content that maximizes CLICK RATE (weighted 70% in scoring).

═══════════════════════════════════════════════
  STRICT CONTENT CONSTRAINTS — MUST FOLLOW
═══════════════════════════════════════════════

1. EMAIL SUBJECT:
   - ONLY English text allowed
   - NO special characters, NO URLs, NO HTML tags
   - Keep it compelling, under 60 characters
   - Must be relevant to the product and segment

2. EMAIL BODY:
   - ONLY English text and emojis (🎯 💰 ✨ 🏦 📈 etc.) allowed
   - Must contain EXACTLY ONE URL: {REQUIRED_URL}
   - The URL must appear as a clickable link: <a href="{REQUIRED_URL}">Explore XDeposit Now</a>
   - Apply HTML font variations where appropriate:
     • <b>bold</b> for key benefits and numbers
     • <i>italic</i> for emphasis and emotional appeal
     • <u>underline</u> for the call-to-action
   - No other URLs allowed anywhere in the body
   - Write in a tone appropriate for the BFSI industry

3. CLICK OPTIMIZATION:
   - The call-to-action must be prominent and compelling
   - Use urgency and value propositions to drive clicks
   - Place the link strategically (mid-body + end)
   - Keep the email concise — under 200 words

RESPONSE FORMAT — Return ONLY this JSON:
{{
  "subject": "<email subject line>",
  "body": "<HTML email body>",
  "variants": [
    {{"subject": "<variant 2 subject>", "body": "<variant 2 body>"}},
    {{"subject": "<variant 3 subject>", "body": "<variant 3 body>"}}
  ]
}}

Respond with ONLY the JSON — no markdown fences, no explanation."""


# ─── Agent Node ───────────────────────────────────────────────────────────────


def creative_node(state: CampaignState) -> Dict[str, Any]:
    """
    LangGraph node: Generate email subject + body with strict constraints.

    Reads:  state["plan"], state["cohort"], state["recipient_emails"],
            state["compliance_issues"] (on retry)
    Writes: state["email_subject"], state["email_body"],
            state["content_variants"], state["logs"], state["status"]
    """
    plan = state.get("plan", {})
    logs = list(state.get("logs", []))
    compliance_issues = state.get("compliance_issues", [])
    retries = state.get("compliance_retries", 0)

    # Build context for the LLM
    product = plan.get("product", "XDeposit")
    segment = plan.get("segment", "all")
    tone = plan.get("tone", "professional")
    value_props = plan.get("value_props", [])
    interest_rate = plan.get("interest_rate_bonus")
    cohort_size = len(state.get("recipient_emails", []))

    # If retrying after compliance rejection, include the issues
    compliance_feedback = ""
    if compliance_issues and retries > 0:
        compliance_feedback = (
            f"\n\n⚠️ COMPLIANCE REJECTION — Fix these issues:\n"
            + "\n".join(f"  - {issue}" for issue in compliance_issues)
            + "\n\nGenerate NEW content that addresses ALL issues above."
        )

    logs.append({
        "agent": "creative",
        "action": "generating_content",
        "detail": f"Creating email for {product} targeting {segment} ({cohort_size} recipients). Attempt {retries + 1}.",
    })

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.7,  # Higher for creative variety
        )

        messages = [
            SystemMessage(content=CREATIVE_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Generate email content for this campaign:\n\n"
                f"Product: {product}\n"
                f"Target Segment: {segment}\n"
                f"Tone: {tone}\n"
                f"Value Propositions: {', '.join(value_props)}\n"
                f"Interest Rate Bonus: {interest_rate or 'Not specified'}\n"
                f"Recipients: {cohort_size} customers\n"
                f"Required URL: {REQUIRED_URL}"
                f"{compliance_feedback}"
            )),
        ]

        response = llm.invoke(messages)
        raw_text = response.content.strip()

        # Clean markdown
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

        content = json.loads(raw_text)

        subject = content.get("subject", f"Discover {product} — Exclusive Offer Inside")
        body = content.get("body", "")
        variants = content.get("variants", [])

        # Ensure the required URL is in the body
        if REQUIRED_URL not in body:
            body += f'\n\n<p><u><a href="{REQUIRED_URL}">Explore {product} Now →</a></u></p>'

        logs.append({
            "agent": "creative",
            "action": "content_generated",
            "detail": f"Subject: '{subject[:50]}...' | Body length: {len(body)} chars | Variants: {len(variants)}",
        })

        return {
            "email_subject": subject,
            "email_body": body,
            "content_variants": variants,
            "logs": logs,
            "status": "content_ready",
        }

    except Exception as e:
        logs.append({
            "agent": "creative",
            "action": "error",
            "detail": f"Creative generation failed: {e}. Using fallback content.",
        })

        # Fallback content
        fallback_subject = f"Exclusive {product} Opportunity — Don't Miss Out"
        fallback_body = (
            f"<p>Dear Valued Customer,</p>"
            f"<p>We're excited to introduce <b>{product}</b> — "
            f"your gateway to <i>smarter financial growth</i>. 💰</p>"
            f"<p><b>Key Benefits:</b></p>"
            f"<ul>"
            + "".join(f"<li>{vp}</li>" for vp in (value_props or ["High returns", "Secure investment"]))
            + f"</ul>"
            f"<p>{'📈 <b>Special Bonus: ' + interest_rate + ' additional interest rate!</b>' if interest_rate else ''}</p>"
            f'<p><u><a href="{REQUIRED_URL}">✨ Explore {product} Now →</a></u></p>'
            f"<p>Warm regards,<br><i>SuperBFSI Team</i> 🏦</p>"
        )

        return {
            "email_subject": fallback_subject,
            "email_body": fallback_body,
            "content_variants": [],
            "logs": logs,
            "status": "content_ready",
            "errors": list(state.get("errors", [])) + [f"Creative error: {e}"],
        }
