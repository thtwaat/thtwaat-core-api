#!/usr/bin/env python3
"""Generate Phase 4 marketplace prompt JSON seeds (100 templates).

Idempotent UUIDs via uuid5(slug). Safe to re-run.

Usage:
  python scripts/generate_marketplace_prompt_seeds.py
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "marketplace" / "seeds" / "prompts"
INDEX = ROOT / "data" / "marketplace" / "seeds" / "index.json"
NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

CATALOG: dict[str, list[tuple[str, str, str]]] = {
    "writing": [
        ("blog-outline", "Blog Outline Writer", "structured blog outlines"),
        ("blog-draft", "Long-form Blog Drafter", "full draft articles"),
        ("seo-meta", "SEO Meta Copywriter", "title and meta descriptions"),
        ("newsletter", "Newsletter Composer", "email newsletters"),
        ("linkedin-post", "LinkedIn Post Writer", "professional social posts"),
        ("press-release", "Press Release Writer", "company announcements"),
        ("product-description", "Product Description Writer", "e-commerce copy"),
        ("rewrite-clarity", "Clarity Rewriter", "simplifying dense text"),
        ("story-hook", "Story Hook Generator", "opening hooks"),
    ],
    "coding": [
        ("code-review", "Code Review Assistant", "PR review feedback"),
        ("bug-explainer", "Bug Explainer", "root-cause analysis"),
        ("unit-test-gen", "Unit Test Generator", "test cases"),
        ("api-docs", "API Docs Writer", "OpenAPI-style docs"),
        ("sql-optimizer", "SQL Query Optimizer", "query performance"),
        ("regex-builder", "Regex Builder", "regular expressions"),
        ("refactor-plan", "Refactor Planner", "safe refactor steps"),
        ("dockerfile-gen", "Dockerfile Generator", "container setup"),
        ("error-triage", "Error Log Triage", "log diagnosis"),
    ],
    "marketing": [
        ("ad-copy", "Ad Copy Generator", "paid ads"),
        ("landing-hero", "Landing Hero Copy", "hero headlines"),
        ("campaign-brief", "Campaign Brief Builder", "campaign planning"),
        ("persona-builder", "Buyer Persona Builder", "audience personas"),
        ("ab-variant", "A/B Variant Writer", "copy variants"),
        ("ugc-script", "UGC Script Writer", "short video scripts"),
        ("launch-email", "Launch Email Sequence", "product launch emails"),
        ("competitor-angle", "Competitor Angle Finder", "differentiation"),
        ("hashtag-pack", "Hashtag Pack Generator", "social hashtags"),
    ],
    "finance": [
        ("expense-summary", "Expense Summary Analyst", "expense narratives"),
        ("invoice-followup", "Invoice Follow-up Writer", "payment reminders"),
        ("budget-narrative", "Budget Narrative Writer", "budget memos"),
        ("cashflow-brief", "Cashflow Briefing", "cash position briefs"),
        ("pricing-memo", "Pricing Strategy Memo", "pricing decisions"),
        ("investor-update", "Investor Update Draft", "investor emails"),
        ("kpi-commentary", "KPI Commentary Writer", "metric narratives"),
        ("risk-note", "Financial Risk Note", "risk summaries"),
    ],
    "hr": [
        ("jd-writer", "Job Description Writer", "job posts"),
        ("interview-scorecard", "Interview Scorecard Builder", "hiring rubrics"),
        ("offer-letter", "Offer Letter Drafter", "offer letters"),
        ("onboarding-plan", "Onboarding Plan Writer", "30-60-90 plans"),
        ("performance-review", "Performance Review Helper", "review feedback"),
        ("policy-summary", "HR Policy Summarizer", "policy plain language"),
        ("rejection-email", "Candidate Rejection Email", "respectful declines"),
        ("engagement-survey", "Engagement Survey Designer", "survey questions"),
    ],
    "legal": [
        ("nda-summary", "NDA Clause Summarizer", "NDA plain English"),
        ("contract-risk", "Contract Risk Spotter", "risky clauses"),
        ("privacy-policy", "Privacy Policy Drafter", "privacy notices"),
        ("tos-outline", "Terms of Service Outline", "ToS structure"),
        ("compliance-checklist", "Compliance Checklist Builder", "compliance tasks"),
        ("dispute-response", "Dispute Response Drafter", "formal responses"),
        ("vendor-dpa", "Vendor DPA Checklist", "data processing agreements"),
        ("legal-faq", "Legal FAQ Writer", "customer legal FAQs"),
    ],
    "healthcare": [
        ("patient-faq", "Patient FAQ Writer", "clinic FAQs"),
        ("symptom-triage-copy", "Symptom Triage Copy", "non-diagnostic guidance copy"),
        ("appointment-reminder", "Appointment Reminder Writer", "reminders"),
        ("care-plan-summary", "Care Plan Summarizer", "care summaries"),
        ("consent-form", "Consent Form Plain-language", "consent text"),
        ("clinic-blog", "Clinic Blog Assistant", "health education posts"),
        ("insurance-explain", "Insurance Benefit Explainer", "coverage explanations"),
        ("discharge-notes", "Discharge Notes Simplifier", "patient-friendly notes"),
    ],
    "education": [
        ("lesson-plan", "Lesson Plan Builder", "class plans"),
        ("quiz-generator", "Quiz Generator", "assessments"),
        ("rubric-builder", "Grading Rubric Builder", "rubrics"),
        ("study-guide", "Study Guide Writer", "exam prep"),
        ("parent-update", "Parent Update Email", "school updates"),
        ("course-outline", "Course Outline Designer", "syllabi"),
        ("socratic-tutor", "Socratic Tutor Prompt", "guided questioning"),
        ("essay-feedback", "Essay Feedback Coach", "constructive critique"),
    ],
    "research": [
        ("lit-review", "Literature Review Assistant", "paper synthesis"),
        ("research-question", "Research Question Refiner", "RQ sharpening"),
        ("method-outline", "Methods Outline Writer", "methodology"),
        ("citation-helper", "Citation Formatter Helper", "reference formatting"),
        ("abstract-writer", "Abstract Writer", "paper abstracts"),
        ("gap-finder", "Research Gap Finder", "open questions"),
        ("survey-design", "Survey Design Assistant", "research surveys"),
        ("findings-summary", "Findings Summarizer", "results narratives"),
    ],
    "ai_agents": [
        ("customer-support-agent", "Customer Support Agent Prompt", "support bots"),
        ("sales-qualifier", "Sales Qualifier Agent", "lead qualification"),
        ("knowledge-rag", "Knowledge RAG Assistant", "doc Q&A"),
        ("ops-runbook", "Ops Runbook Agent", "incident runbooks"),
        ("meeting-secretary", "Meeting Secretary Agent", "meeting notes"),
        ("onboarding-concierge", "Onboarding Concierge Agent", "product onboarding"),
        ("moderation-agent", "Content Moderation Agent", "safety checks"),
        ("scheduler-agent", "Scheduling Agent Prompt", "calendar coordination"),
        ("analytics-agent", "Analytics Explainer Agent", "metric Q&A"),
    ],
    "business": [
        ("okrs-writer", "OKR Writer", "objectives and key results"),
        ("meeting-agenda", "Meeting Agenda Builder", "agendas"),
        ("decision-memo", "Decision Memo Writer", "decision records"),
        ("sop-writer", "SOP Writer", "standard operating procedures"),
        ("swot-analysis", "SWOT Analysis Facilitator", "SWOT"),
        ("vendor-rfp", "Vendor RFP Drafter", "RFP sections"),
        ("partnership-pitch", "Partnership Pitch Writer", "partner outreach"),
        ("status-report", "Weekly Status Report", "team updates"),
    ],
    "analytics": [
        ("metric-definition", "Metric Definition Writer", "KPI definitions"),
        ("dashboard-narrative", "Dashboard Narrative", "chart stories"),
        ("funnel-analysis", "Funnel Analysis Explainer", "conversion funnels"),
        ("cohort-summary", "Cohort Summary Writer", "cohort insights"),
        ("anomaly-explain", "Anomaly Explainer", "spike/dip hypotheses"),
        ("experiment-design", "Experiment Design Brief", "A/B experiments"),
        ("sql-brief", "Analytics SQL Brief", "analysis asks"),
        ("executive-insight", "Executive Insight Card", "one-page insights"),
    ],
}

SYSTEM_ROLES = {
    "writing": "You are an expert professional writer.",
    "coding": "You are a senior software engineer and code reviewer.",
    "marketing": "You are a performance marketing strategist and copywriter.",
    "finance": "You are a careful finance analyst. Never invent numbers.",
    "hr": "You are an experienced HR business partner.",
    "legal": "You are a legal drafting assistant. This is not legal advice; flag that clearly.",
    "healthcare": "You are a healthcare communications assistant. Do not diagnose or prescribe.",
    "education": "You are an instructional designer and educator.",
    "research": "You are a rigorous research assistant.",
    "ai_agents": "You are designing production-ready system prompts for AI agents.",
    "business": "You are an operating executive and business operator.",
    "analytics": "You are a product analytics lead.",
}

TEMPS = {
    "writing": 0.7,
    "coding": 0.2,
    "marketing": 0.75,
    "finance": 0.3,
    "hr": 0.5,
    "legal": 0.2,
    "healthcare": 0.35,
    "education": 0.55,
    "research": 0.4,
    "ai_agents": 0.35,
    "business": 0.45,
    "analytics": 0.3,
}

EXAMPLE_INPUT = {
    "writing": "Audience: founders. Goal: publish a post about AI onboarding. Tone: practical.",
    "coding": "Language: TypeScript. Code: flaky async test. Constraints: no new deps.",
    "marketing": "Audience: SMB owners. Goal: trial signups. Tone: direct.",
    "finance": "Period: Q2. Audience: board. Figures: burn $120k, runway 9 months.",
    "hr": "Audience: hiring managers. Goal: backend engineer JD. Tone: inclusive.",
    "legal": "Excerpt: mutual NDA draft. Jurisdiction: India. Risk: moderate.",
    "healthcare": "Audience: patients. Topic: preparing for first physio visit.",
    "education": "Audience: grade 9. Goal: photosynthesis lesson. Tone: clear.",
    "research": "Question: impact of RAG on support deflection. Sources: 3 papers.",
    "ai_agents": "Product: billing helpdesk. Tools: ticket API, KB search.",
    "business": "Audience: leadership. Goal: decide pricing change. Tone: crisp.",
    "analytics": "Question: why activation dropped 12%. Data: weekly funnel.",
}


def vars_for(category: str) -> list[dict]:
    if category == "coding":
        return [
            {"name": "language", "label": "Language / stack", "required": True},
            {"name": "code_or_error", "label": "Code or error", "required": True},
            {"name": "constraints", "label": "Constraints", "required": False},
        ]
    if category == "finance":
        return [
            {"name": "period", "label": "Period", "required": True},
            {"name": "figures", "label": "Known figures (only facts)", "required": False},
            {"name": "audience", "label": "Audience", "required": True},
        ]
    if category == "legal":
        return [
            {"name": "jurisdiction", "label": "Jurisdiction (if known)", "required": False},
            {"name": "document_excerpt", "label": "Document excerpt", "required": True},
            {"name": "risk_tolerance", "label": "Risk tolerance", "required": False},
        ]
    if category == "healthcare":
        return [
            {"name": "audience", "label": "Audience", "required": True},
            {"name": "topic", "label": "Topic", "required": True},
            {"name": "disclaimer_needed", "label": "Include medical disclaimer", "required": False},
        ]
    if category in ("research", "analytics"):
        return [
            {"name": "question", "label": "Primary question", "required": True},
            {"name": "data_or_sources", "label": "Data / sources", "required": False},
            {"name": "constraints", "label": "Constraints", "required": False},
        ]
    if category == "ai_agents":
        return [
            {"name": "product", "label": "Product / domain", "required": True},
            {"name": "tools", "label": "Tools available", "required": False},
            {"name": "guardrails", "label": "Guardrails", "required": False},
        ]
    return [
        {"name": "audience", "label": "Audience", "required": True},
        {"name": "goal", "label": "Goal", "required": True},
        {"name": "context", "label": "Context / notes", "required": False},
        {"name": "tone", "label": "Tone", "required": False},
    ]


def prompt_text(category: str, name: str, focus: str) -> str:
    role = SYSTEM_ROLES[category]
    return (
        f"{role}\n\n"
        f"Task: Produce high-quality output for {focus} using the template '{name}'.\n"
        "Requirements:\n"
        "- Follow the user variables exactly.\n"
        "- Be specific, structured, and actionable.\n"
        "- Call out assumptions explicitly.\n"
        "- If information is missing, ask concise clarifying questions first.\n"
        "- Prefer bullet points and short sections over walls of text.\n"
    )


def main() -> None:
    total = sum(len(v) for v in CATALOG.values())
    if total != 100:
        raise SystemExit(f"Expected 100 templates, catalog has {total}")

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()

    tiers_cycle = ["free", "free", "free", "starter", "pro"]
    templates: list[dict] = []
    i = 0
    for category, items in CATALOG.items():
        for slug_suffix, name, focus in items:
            i += 1
            slug = f"{category.replace('_', '-')}-{slug_suffix}"
            tid = str(uuid.uuid5(NS, f"thtwaat:marketplace:prompt:{slug}"))
            tier = tiers_cycle[i % len(tiers_cycle)]
            featured = i % 11 == 0
            tags = [category.replace("_", "-"), slug_suffix.split("-")[0], "prompt", "thtwaat"]
            if featured:
                tags.append("featured")
            ex_out = (
                f"## {name}\n"
                f"- Objective: {focus}\n"
                "- Assumptions: listed briefly\n"
                "- Deliverable: structured draft ready to edit\n"
                "- Next steps: 2-3 concrete actions\n"
            )
            doc = {
                "id": tid,
                "slug": slug,
                "name": name,
                "description": f"Production prompt template for {focus}.",
                "category": category,
                "kind": "agent" if category == "ai_agents" else "prompt",
                "prompt": prompt_text(category, name, focus),
                "variables": vars_for(category),
                "temperature": TEMPS[category],
                "tags": tags,
                "visibility": "public",
                "featured": featured,
                "version": "1.0.0",
                "example_input": EXAMPLE_INPUT[category],
                "example_output": ex_out,
                "pricing_tier": tier,
                "author": "THTWAAT",
                "industry": category,
            }
            (OUT / f"{slug}.json").write_text(
                json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            templates.append(
                {
                    "id": tid,
                    "slug": slug,
                    "category": category,
                    "name": name,
                    "file": f"prompts/{slug}.json",
                    "featured": featured,
                    "pricing_tier": tier,
                    "kind": doc["kind"],
                }
            )

    index = {
        "version": "1.0.0",
        "count": len(templates),
        "categories": sorted(CATALOG.keys()),
        "templates": templates,
    }
    INDEX.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(templates)} templates to {OUT}")
    print(f"Index: {INDEX}")


if __name__ == "__main__":
    main()
