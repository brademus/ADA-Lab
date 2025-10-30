from pathlib import Path
from ada.dashboard import render_master_index
from ada.clients import ClientConfig
import json


def test_dashboard_shows_outreach_columns(tmp_path: Path):
    audits = tmp_path / 'audits'; audits.mkdir()
    # Fake one client dir with summary.json and outreach_metrics.json
    cslug = 'acme'; cdir = audits / cslug; cdir.mkdir()
    (cdir / 'summary.json').write_text(json.dumps({
        'mean_quality': 7.5,
        'dormant_pct': 12.3,
        'owner_imbalance_pct': 5.0,
        'ts_utc': '2024-01-01T00:00:00Z'
    }), encoding='utf-8')
    (cdir / 'outreach_metrics.json').write_text(json.dumps({
        'emails_drafted': 5,
        'emails_sent': 3,
        'replies': 1,
        'meetings': 0,
        'reply_rate': 0.33,
    }), encoding='utf-8')
    out = audits / 'index.html'
    render_master_index([ClientConfig(slug=cslug, name='Acme', overrides={})], audits, out)
    html = out.read_text(encoding='utf-8')
    assert 'Emails Drafted' in html
    assert 'Emails Sent' in html
    assert '>5<' in html  # drafted
    assert '>3<' in html  # sent
    assert '>1<' in html  # replies
