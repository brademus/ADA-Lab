from pathlib import Path
from ada.templates.library import get_variants_for_set, load_library
from ada.orchestrator import templates
from ada.core.schemas import Contact
import json

def test_load_yaml_and_render_variant(tmp_path: Path):
    lib = tmp_path
    lib.mkdir(parents=True, exist_ok=True)
    yml = lib / "baseline.yml"
    yml.write_text(
        """
variant_set: baseline
variants:
  - id: v1
    name: Welcome
    subject_tpl: "Hi {first_name}"
    body_tpl: "Body for {email}"
        """,
        encoding="utf-8",
    )
    vs = get_variants_for_set(lib, "baseline")
    assert len(vs) == 1
    v = vs[0]
    c = Contact(id="1", email="a@example.com", first_name="Ada", last_name=None, owner_id=None, lifecycle=None, last_modified=None, score=None)
    subj, body = templates.render_variant(c, v)
    assert subj == "Hi Ada"
    assert "a@example.com" in body


def test_load_json_default_variant_set_from_filename(tmp_path: Path):
    lib = tmp_path
    data = {
        "variants": [
            {"id": "v2", "name": "Alt", "subject_tpl": "Hello {first_name}", "body_tpl": "B"}
        ]
    }
    (lib / "alt.json").write_text(json.dumps(data), encoding="utf-8")
    libs = load_library(lib)
    assert "alt" in libs
    assert libs["alt"][0].id == "v2"


def test_brand_voice_used_in_legacy_renderer():
    c = Contact(id="1", email="a@example.com", first_name="Ada", last_name=None, owner_id=None, lifecycle=None, last_modified=None, score=None)
    subj, _ = templates.render(c, brand_voice="Curious, friendly")
    assert subj.startswith("Curious")
