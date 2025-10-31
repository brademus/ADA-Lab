from __future__ import annotations

import sys
from pathlib import Path

from .clients import ClientConfig
from .dashboard import render_master_index


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "audits")
    if not root.exists():
        print("No audits/ directory present")
        return 0
    clients = []
    for p in sorted([d for d in root.iterdir() if d.is_dir()]):
        slug = p.name
        clients.append(ClientConfig(slug=slug, name=slug.replace("_", " ").title(), overrides={}))
    if not clients:
        print("No client directories under audits/")
        return 0
    render_master_index(clients, root, root / "index.html")
    print("Rendered index for clients:", [c.slug for c in clients])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
