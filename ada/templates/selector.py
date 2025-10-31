from __future__ import annotations


def choose_variant(fit_score: float, company_size: str | None) -> str:
    # Simple bands: high score -> short; mid -> medium; low -> value
    size = (company_size or "").lower()
    if fit_score >= 80:
        return "short"
    if fit_score >= 50:
        # larger companies get medium
        if any(s in size for s in ["200", "500", "1000", "enterprise", "large"]):
            return "medium"
        return "short"
    return "value"
