import json
from pathlib import Path

from ada.clients import ClientConfig
from ada.dashboard import render_master_index


def test_dashboard_variant_panel_renders(tmp_path: Path):
    audits_root = tmp_path
    slug = "foo"
    cdir = audits_root / slug
    cdir.mkdir(parents=True, exist_ok=True)
    summary = {
        "mean_quality": 50.0,
        "dormant_pct": 10.0,
        "owner_imbalance_pct": 0.0,
        "ts_utc": "2025-10-26T00:00:00Z",
        "variant_perf": [
            {
                "variant_id": "A",
                "sent": 10,
                "opens": 6,
                "replies": 3,
                "meetings": 1,
                "reply_rate": 0.3,
                "conversion_rate": 0.1,
            },
            {
                "variant_id": "B",
                "sent": 8,
                "opens": 5,
                "replies": 2,
                "meetings": 0,
                "reply_rate": 0.25,
                "conversion_rate": 0.0,
            },
        ],
    }
    (cdir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    out = audits_root / "index.html"
    cfg = ClientConfig(slug=slug, name="Foo", hubspot_token=None, overrides={})
    render_master_index([cfg], audits_root, out)
    html = out.read_text(encoding="utf-8")
    assert "Variants & Tests — Foo (foo)" in html
    assert ">A<" in html or "A</td>" in html
