from __future__ import annotations
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from pathlib import Path
import re

try:
    import tomllib  # py311+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # optional


class ClientConfig(BaseModel):
    """Strongly-typed client configuration for Consultant Mode."""
    slug: str = Field(..., description="Stable machine slug (e.g., 'acme_corp').")
    name: str = Field(..., description="Human readable client name.")
    hubspot_token: str = Field(..., description="HubSpot Private App Access Token (PAT).")
    overrides: Dict[str, Any] = Field(default_factory=dict, description="Optional per-client overrides.")


_slug_non_alnum = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """
    Convert a string into a safe slug: lowercase, underscores, no leading/trailing underscores.
    """
    s = name.strip().lower()
    s = _slug_non_alnum.sub("_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _load_toml(path: Path) -> Dict[str, Dict[str, Any]]:
    with path.open("rb") as f:
        data = tomllib.load(f)
    if not isinstance(data, dict):
        raise ValueError("clients.toml must contain a table of client sections")
    return data


def _load_yaml(path: Path) -> Dict[str, Dict[str, Any]]:
    if yaml is None:
        raise RuntimeError("PyYAML is not installed; cannot parse YAML client config.")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("clients.yaml must contain a mapping of client sections")
    return data


def load_clients(path: str) -> List[ClientConfig]:
    """
    Load client configs from TOML or YAML. Top-level keys like:
      [client_acme_corp] → slug 'acme_corp' (strip 'client_' prefix).
    Required fields per section: name, hubspot_token. Optional: overrides.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Client config not found: {p}")

    if p.suffix.lower() in (".toml",):
        raw = _load_toml(p)
    elif p.suffix.lower() in (".yaml", ".yml"):
        raw = _load_yaml(p)
    else:
        raise ValueError("Unsupported config type; use .toml or .yaml")

    clients: List[ClientConfig] = []
    for section_key, cfg in raw.items():
        if not isinstance(cfg, dict):
            continue
        key = section_key
        if key.startswith("client_"):
            key = key[len("client_") :]
        slug = slugify(key)
        name = cfg.get("name") or slug.replace("_", " ").title()
        token = cfg.get("hubspot_token")
        if not token:
            raise ValueError(f"Missing 'hubspot_token' for section [{section_key}]")
        overrides = cfg.get("overrides") or {}
        clients.append(ClientConfig(slug=slug, name=name, hubspot_token=token, overrides=overrides))
    if not clients:
        raise ValueError("No clients loaded from config.")
    return clients


def get_client(clients: List[ClientConfig], slug: str) -> ClientConfig:
    """Find a client by slug (case-insensitive)."""
    target = slugify(slug)
    for c in clients:
        if c.slug == target:
            return c
    raise KeyError(f"Client '{slug}' not found. Available: {[c.slug for c in clients]}")
