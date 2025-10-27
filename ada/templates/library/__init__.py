from __future__ import annotations
from pathlib import Path
from typing import Dict, List
import json
import yaml
from ada.learning.variants import Variant


def load_library(path: Path) -> Dict[str, List[Variant]]:
    """Load all YAML/JSON files in a templates/library directory and return mapping
    of variant_set -> list[Variant]. Files may contain a top-level 'variant_set'
    or default to filename (without ext).
    """
    libs: Dict[str, List[Variant]] = {}
    path.mkdir(parents=True, exist_ok=True)
    for p in sorted(path.glob("*")):
        if not p.is_file():
            continue
        try:
            if p.suffix.lower() in (".yml", ".yaml"):
                payload = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            elif p.suffix.lower() == ".json":
                payload = json.loads(p.read_text(encoding="utf-8"))
            else:
                continue
            vs = payload.get("variant_set") or p.stem
            variants = []
            for v in payload.get("variants", []):
                variants.append(Variant(**v))
            libs[vs] = variants
        except Exception:
            # skip invalid files but continue
            continue
    return libs


def get_variants_for_set(path: Path, variant_set: str):
    libs = load_library(path)
    return libs.get(variant_set, [])
