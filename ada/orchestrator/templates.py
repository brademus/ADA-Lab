from __future__ import annotations

from ada.core.schemas import Contact
from ada.learning.variants import Variant


def render_subject(
    contact: Contact, brand_voice: str | None = None, offer: str | None = None
) -> str:
    prefix = "Quick question" if not brand_voice else brand_voice.split(",")[0]
    name = contact.first_name or contact.email or "there"
    return f"{prefix} for {name}"


def render_body(contact: Contact, brand_voice: str | None = None, offer: str | None = None) -> str:
    lines = []
    if brand_voice:
        lines.append(f"Tone: {brand_voice}")
    lines.append(f"Hi {contact.first_name or contact.email or 'there'},")
    if offer:
        lines.append(offer)
    else:
        lines.append("I wanted to share something I think will help your team.")
    lines.append("Best,\nYour team")
    return "\n\n".join(lines)


def render(
    contact: Contact, brand_voice: str | None = None, offer: str | None = None
) -> tuple[str, str]:
    """Backward compatible renderer used when no variant is selected."""
    return render_subject(contact, brand_voice, offer), render_body(contact, brand_voice, offer)


def render_variant(contact: Contact, variant: Variant) -> tuple[str, str]:
    """Render subject and body from a Variant's templates.

    Variant templates are simple Python-format templates that receive 'contact'
    mapping with keys like first_name, email.
    """
    ctx = {
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "email": contact.email,
    }
    try:
        subj = variant.subject_tpl.format(**ctx)
    except Exception:
        subj = variant.name
    try:
        body = variant.body_tpl.format(**ctx)
    except Exception:
        body = f"Hi {contact.first_name or contact.email or 'there'},\n\n{variant.name}"
    return subj, body
