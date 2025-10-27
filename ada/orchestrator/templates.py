from __future__ import annotations
from ada.core.schemas import Contact
from typing import Tuple, Optional


def render_subject(contact: Contact, brand_voice: str | None = None, offer: str | None = None) -> str:
    prefix = "Quick question" if not brand_voice else brand_voice.split(",")[0]
    name = contact.first_name or contact.email or "there"
    return f"{prefix} for {name}"


def render_body(contact: Contact, brand_voice: str | None = None, offer: Optional[str] = None) -> str:
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


def render(contact: Contact, brand_voice: str | None = None, offer: str | None = None) -> Tuple[str, str]:
    return render_subject(contact, brand_voice, offer), render_body(contact, brand_voice, offer)
