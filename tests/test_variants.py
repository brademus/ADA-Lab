from pathlib import Path

from ada.learning import variants as ve


def test_choose_variant_exploitation(tmp_path: Path):
    audits_root = tmp_path
    slug = "acme"
    db = audits_root / slug / "learning.sqlite"
    ve.init_learning_db(db)

    v1 = ve.Variant(id="A", name="A", subject_tpl="Hello {first_name}", body_tpl="Body")
    v2 = ve.Variant(id="B", name="B", subject_tpl="Hello {first_name}", body_tpl="Body")
    pool = [v1, v2]

    # With no stats, epsilon=0 picks the first variant by default
    chosen = ve.choose_variant(pool, audits_root, slug, variant_set="baseline", epsilon=0.0)
    assert chosen.id == "A"

    # Make B the better performer: B has replies, A has none
    for _ in range(10):
        ve.record_event(db, "baseline", "A", "sent")
    for _ in range(10):
        ve.record_event(db, "baseline", "B", "sent")
    for _ in range(5):
        ve.record_event(db, "baseline", "B", "replied")

    # With epsilon=0 (pure exploitation), B should be chosen
    chosen2 = ve.choose_variant(pool, audits_root, slug, variant_set="baseline", epsilon=0.0)
    assert chosen2.id == "B"


def test_choose_variant_exploration_happens(tmp_path: Path):
    audits_root = tmp_path
    slug = "acme"
    db = audits_root / slug / "learning.sqlite"
    ve.init_learning_db(db)

    v1 = ve.Variant(id="A", name="A", subject_tpl="S", body_tpl="B")
    v2 = ve.Variant(id="B", name="B", subject_tpl="S", body_tpl="B")

    # Force random selection and ensure both variants appear across many trials
    seen = set()
    for _ in range(100):
        ch = ve.choose_variant([v1, v2], audits_root, slug, variant_set="baseline", epsilon=1.0)
        seen.add(ch.id)
        if len(seen) == 2:
            break
    assert seen == {"A", "B"}
