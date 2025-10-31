import json
from pathlib import Path

from ada.clients import ClientConfig
from ada.dashboard import collect_metrics, render_master_index


def make_client_dir(tmpdir: Path, slug: str):
    d = tmpdir / slug
    d.mkdir()
    # write minimal lead_scores.csv
    (d / "lead_scores.csv").write_text("id,lead_score\n1,50\n2,80\n")
    # write summary.json
    summary = {
        "contacts": 2,
        "mean_quality": 65.0,
        "p50_quality": 65.0,
        "p90_quality": 80.0,
        "dormant_count": 0,
        "dormant_pct": 0.0,
        "owner_imbalance_pct": 0.0,
        "ts_utc": "2025-01-01T00:00:00+00:00",
    }
    (d / "summary.json").write_text(json.dumps(summary))
    (d / "summary.md").write_text("# Summary\n\nGenerated")
    return d


def test_collect_metrics_and_render(tmp_path):
    root = tmp_path / "audits"
    root.mkdir()
    clients = []
    for slug, name in [("alpha", "Alpha Co"), ("beta", "Beta LLC")]:
        make_client_dir(root, slug)
        clients.append(ClientConfig(slug=slug, name=name))

    # collect metrics for one
    m = collect_metrics(root / "alpha")
    assert m["mean_quality"] == 65.0
    assert m["dormant_pct"] == 0.0

    # render index
    out = root / "index.html"
    render_master_index(clients, root, out)
    txt = out.read_text()
    assert "Alpha Co" in txt
    assert "Beta LLC" in txt
    assert "alpha/summary.md" in txt or "alpha/summary.html" in txt
