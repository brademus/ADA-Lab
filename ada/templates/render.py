from __future__ import annotations
from pathlib import Path
from typing import Dict, Tuple


TEMPLATES = {
    'short': 'short.txt',
    'medium': 'medium.txt',
    'value': 'value_prop.txt',
}


def load_template(name: str) -> str:
    fn = TEMPLATES.get(name, name)
    base = Path(__file__).parent
    with open(base / fn, 'r', encoding='utf-8') as f:
        return f.read()


def render_template(name: str, ctx: Dict[str, str]) -> Tuple[str, str]:
    raw = load_template(name)
    # naive split: subject on first line starting with 'Subject:'
    lines = raw.splitlines()
    subject_line = lines[0] if lines else ''
    subject = subject_line.replace('Subject:', '').strip().format(**ctx)
    body = "\n".join(lines[1:]).format(**ctx)
    return subject, body
