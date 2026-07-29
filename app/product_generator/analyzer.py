"""Rule-based prompt analyzer for Product Generator (no LLM required).

Extracts industry, product type, features, brand tone, and language from a
natural-language product prompt. Deterministic and production-safe.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


INDUSTRY_KEYWORDS: Dict[str, List[str]] = {
    "restaurant": ["restaurant", "cafe", "food", "dining", "menu", "ordering", "kitchen", "chef"],
    "healthcare": ["clinic", "hospital", "doctor", "patient", "medical", "health", "dental", "pharmacy"],
    "real_estate": ["real estate", "property", "realtor", "housing", "apartment", "listing", "broker"],
    "education": ["school", "university", "college", "admission", "student", "course", "tuition", "campus"],
    "finance": ["bank", "finance", "loan", "insurance", "fintech", "investment", "accounting"],
    "legal": ["law", "legal", "attorney", "lawyer", "firm", "compliance"],
    "ecommerce": ["shop", "store", "ecommerce", "e-commerce", "retail", "cart", "checkout", "product catalog"],
    "crm": ["crm", "sales pipeline", "leads crm", "customer relationship"],
    "helpdesk": ["helpdesk", "support desk", "ticketing", "customer support"],
    "saas": ["saas", "dashboard", "subscription", "b2b platform"],
}

PRODUCT_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "landing": ["landing", "landing page", "campaign", "lead gen", "lead generation", "one page"],
    "website": ["website", "site", "web site", "portal", "brochure"],
    "saas": ["saas", "dashboard", "portal app", "admin panel", "booking saas", "platform"],
    "crm": ["crm"],
    "helpdesk": ["helpdesk", "support"],
    "ecommerce": ["ecommerce", "e-commerce", "online store", "shop"],
}

FEATURE_KEYWORDS: Dict[str, List[str]] = {
    "ai_chat": ["ai", "chat", "assistant", "bot", "conversational"],
    "ordering": ["order", "ordering", "menu", "cart"],
    "booking": ["book", "booking", "appointment", "schedule", "reservation"],
    "payments": ["payment", "billing", "checkout", "stripe", "razorpay", "invoice"],
    "knowledge": ["knowledge", "faq", "docs", "rag", "search"],
    "leads": ["lead", "enquiry", "inquiry", "contact form", "demo"],
    "domains": ["domain", "custom domain", "ssl"],
    "widget": ["widget", "embed"],
    "multilingual": ["multilingual", "multi-language", "i18n"],
    "analytics": ["analytics", "metrics", "usage"],
    "admissions": ["admission", "enroll", "enrolment", "enrollment"],
    "listings": ["listing", "listings", "catalog", "inventory"],
}

TONE_KEYWORDS: Dict[str, List[str]] = {
    "professional": ["professional", "corporate", "formal", "enterprise"],
    "friendly": ["friendly", "warm", "welcoming", "casual"],
    "luxury": ["luxury", "premium", "elegant", "high-end"],
    "playful": ["playful", "fun", "bold", "vibrant"],
    "clinical": ["clinical", "medical", "precise", "trustworthy"],
    "educational": ["educational", "academic", "informative"],
}

LANGUAGE_KEYWORDS: Dict[str, List[str]] = {
    "hi": ["hindi", "हिंदी", "hinglish"],
    "ar": ["arabic", "عربي"],
    "es": ["spanish", "español"],
    "fr": ["french", "français"],
    "de": ["german", "deutsch"],
    "en": ["english"],
}

# product_type → preferred marketplace category (TemplateCategory values)
TYPE_TO_CATEGORY: Dict[str, str] = {
    "landing": "landing",
    "website": "website",
    "saas": "saas",
    "crm": "crm",
    "helpdesk": "helpdesk",
    "ecommerce": "ecommerce",
}

INDUSTRY_DEFAULT_TYPE: Dict[str, str] = {
    "restaurant": "website",
    "healthcare": "saas",
    "real_estate": "landing",
    "education": "saas",
    "finance": "saas",
    "legal": "website",
    "ecommerce": "ecommerce",
    "crm": "crm",
    "helpdesk": "helpdesk",
    "saas": "saas",
}

INDUSTRY_COLORS: Dict[str, Dict[str, str]] = {
    "restaurant": {"primary": "#C2410C", "accent": "#FDBA74", "theme": "warm"},
    "healthcare": {"primary": "#0F766E", "accent": "#99F6E4", "theme": "light"},
    "real_estate": {"primary": "#1E3A5F", "accent": "#93C5FD", "theme": "light"},
    "education": {"primary": "#1D4ED8", "accent": "#BFDBFE", "theme": "light"},
    "finance": {"primary": "#0F172A", "accent": "#38BDF8", "theme": "dark"},
    "legal": {"primary": "#312E81", "accent": "#A5B4FC", "theme": "light"},
    "ecommerce": {"primary": "#BE185D", "accent": "#FBCFE8", "theme": "light"},
    "saas": {"primary": "#111827", "accent": "#6EE7B7", "theme": "light"},
    "general": {"primary": "#111827", "accent": "#93C5FD", "theme": "light"},
}

NAV_BY_TYPE: Dict[str, List[str]] = {
    "landing": ["Home", "Features", "Pricing", "FAQ", "Contact"],
    "website": ["Home", "About", "Services", "Blog", "Contact"],
    "saas": ["Dashboard", "Agents", "Knowledge", "Billing", "Settings"],
    "crm": ["Pipeline", "Contacts", "Deals", "Reports"],
    "helpdesk": ["Tickets", "Knowledge", "Agents", "Reports"],
    "ecommerce": ["Shop", "Collections", "Cart", "Account", "Support"],
}


@dataclass
class PromptAnalysis:
    industry: str = "general"
    product_type: str = "website"
    category: str = "website"
    required_features: List[str] = field(default_factory=list)
    brand_tone: str = "professional"
    language: str = "en"
    suggested_name: str = "AI Product"
    confidence: float = 0.5
    keywords_matched: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _score(text: str, lexicon: Dict[str, List[str]]) -> Dict[str, int]:
    scores: Dict[str, int] = {}
    for label, words in lexicon.items():
        score = 0
        for w in words:
            if w in text:
                score += 2 if " " in w else 1
        if score:
            scores[label] = score
    return scores


def _best(scores: Dict[str, int], default: str) -> str:
    if not scores:
        return default
    return max(scores.items(), key=lambda kv: kv[1])[0]


def analyze_prompt(prompt: str) -> PromptAnalysis:
    """Extract structured intent from a free-form product prompt."""
    raw = (prompt or "").strip()
    if len(raw) < 3:
        raise ValueError("Prompt must be at least 3 characters")

    text = raw.lower()
    matched: List[str] = []

    industry_scores = _score(text, INDUSTRY_KEYWORDS)
    type_scores = _score(text, PRODUCT_TYPE_KEYWORDS)
    tone_scores = _score(text, TONE_KEYWORDS)
    lang_scores = _score(text, LANGUAGE_KEYWORDS)

    industry = _best(industry_scores, "general")
    product_type = _best(type_scores, INDUSTRY_DEFAULT_TYPE.get(industry, "website"))

    # Feature extraction
    features: List[str] = []
    for feat, words in FEATURE_KEYWORDS.items():
        for w in words:
            if w in text:
                features.append(feat)
                matched.append(w)
                break

    # Always include AI chat for this platform
    if "ai_chat" not in features:
        features.insert(0, "ai_chat")
    if "widget" not in features:
        features.append("widget")
    if "knowledge" not in features and any(x in text for x in ("faq", "docs", "knowledge")):
        features.append("knowledge")

    brand_tone = _best(tone_scores, "professional")
    if industry == "healthcare" and brand_tone == "professional":
        brand_tone = "clinical"
    if industry == "education" and brand_tone == "professional":
        brand_tone = "educational"

    language = _best(lang_scores, "en")
    category = TYPE_TO_CATEGORY.get(product_type, product_type)

    # Suggested product name from prompt nouns
    suggested = _suggest_name(raw, industry, product_type)

    confidence = 0.4
    if industry_scores:
        confidence += 0.2
    if type_scores:
        confidence += 0.2
    if features:
        confidence += min(0.2, 0.05 * len(features))
    confidence = round(min(confidence, 0.95), 2)

    matched.extend(list(industry_scores.keys()))
    matched.extend(list(type_scores.keys()))

    return PromptAnalysis(
        industry=industry,
        product_type=product_type,
        category=category,
        required_features=features,
        brand_tone=brand_tone,
        language=language,
        suggested_name=suggested,
        confidence=confidence,
        keywords_matched=sorted(set(matched)),
    )


def build_product_config(analysis: PromptAnalysis, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Step 4 — theme, colors, nav, suggested prompts from analysis."""
    colors = INDUSTRY_COLORS.get(analysis.industry, INDUSTRY_COLORS["general"])
    nav = NAV_BY_TYPE.get(analysis.product_type, NAV_BY_TYPE["website"])
    prompts = _suggested_prompts(analysis)

    config: Dict[str, Any] = {
        "name": analysis.suggested_name,
        "industry": analysis.industry,
        "product_type": analysis.product_type,
        "category": analysis.category,
        "brand_tone": analysis.brand_tone,
        "language": analysis.language,
        "theme": colors["theme"],
        "colors": {
            "primary": colors["primary"],
            "accent": colors["accent"],
        },
        "logo_placeholder": f"/brand/{analysis.industry}-logo.svg",
        "navigation": nav,
        "suggested_prompts": prompts,
        "features": analysis.required_features,
        "welcome_message": _welcome(analysis),
        "system_prompt": _system_prompt(analysis),
    }
    if overrides:
        # shallow + nested colors merge
        nested = dict(config)
        nested.update({k: v for k, v in overrides.items() if k != "colors"})
        if "colors" in overrides and isinstance(overrides["colors"], dict):
            nested["colors"] = {**config["colors"], **overrides["colors"]}
        config = nested
    return config


def _suggest_name(prompt: str, industry: str, product_type: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", " ", prompt).strip()
    words = [w for w in cleaned.split() if len(w) > 2][:5]
    if words:
        title = " ".join(w.capitalize() for w in words[:4])
        if len(title) > 48:
            title = title[:45] + "…"
        return title
    return f"{industry.replace('_', ' ').title()} {product_type.title()}"


def _suggested_prompts(analysis: PromptAnalysis) -> List[str]:
    industry = analysis.industry
    mapping = {
        "restaurant": ["Show me the menu", "Place an order", "Book a table", "What are today's specials?"],
        "healthcare": ["Book an appointment", "Clinic hours?", "Insurance accepted?", "Talk to a doctor"],
        "real_estate": ["Show listings nearby", "Schedule a viewing", "Mortgage options?", "Contact an agent"],
        "education": ["Admission process?", "Fee structure", "Apply now", "Campus facilities"],
        "finance": ["Open an account", "Loan eligibility", "Talk to advisor", "Fee schedule"],
        "legal": ["Book a consultation", "Practice areas?", "Upload documents", "Contact lawyer"],
        "ecommerce": ["Track my order", "Return policy?", "Best sellers", "Talk to support"],
        "saas": ["Pricing plans?", "Start free trial", "Book a demo", "How does billing work?"],
    }
    return mapping.get(industry, ["How can you help?", "Pricing?", "Book a demo", "Contact support"])


def _welcome(analysis: PromptAnalysis) -> str:
    name = analysis.suggested_name
    tone = analysis.brand_tone
    if tone == "friendly":
        return f"Hey! Welcome to {name} — how can I help today?"
    if tone == "clinical":
        return f"Welcome to {name}. How may we assist you?"
    if tone == "luxury":
        return f"Welcome to {name}. We're delighted to assist you."
    return f"Hi! I'm the {name} assistant. How can I help?"


def _system_prompt(analysis: PromptAnalysis) -> str:
    features = ", ".join(analysis.required_features) or "general assistance"
    return (
        f"You are the AI assistant for {analysis.suggested_name}, "
        f"a {analysis.product_type} product in the {analysis.industry.replace('_', ' ')} industry. "
        f"Brand tone: {analysis.brand_tone}. Language: {analysis.language}. "
        f"Focus on: {features}. "
        f"Be helpful, accurate, and on-brand. Use the knowledge base when available."
    )
