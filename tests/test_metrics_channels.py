import json

import pandas as pd

from ada.reporting import write_outputs


def test_reporting_merges_by_channel(tmp_path):
    out = tmp_path / "acme"
    out.mkdir()
    # Prepare outreach metrics with channel splits
    outreach = {
        "contacted": 5,
        "replies": 2,
        "meetings": 0,
        "reply_rate": 0.4,
        "contacted_by_channel": {"gmail": 3, "outlook": 2},
        "replies_by_channel": {"gmail": 1, "outlook": 1},
        "meetings_by_channel": {},
    }
    (out / "outreach_metrics.json").write_text(json.dumps(outreach), encoding="utf-8")

    # Minimal DF for write_outputs
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "lead_score": [50, 60, 70],
            "email": ["a@x.com", "b@x.com", "c@x.com"],
        }
    )
    write_outputs(df, str(out))

    # Validate summary.json merged fields
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary.get("contacted") == 5
    assert summary.get("replies") == 2
    assert summary.get("reply_rate") == 0.4
    assert summary.get("contacted_by_channel", {}).get("gmail") == 3
    assert summary.get("contacted_by_channel", {}).get("outlook") == 2
    assert summary.get("replies_by_channel", {}).get("gmail") == 1
    assert summary.get("replies_by_channel", {}).get("outlook") == 1
