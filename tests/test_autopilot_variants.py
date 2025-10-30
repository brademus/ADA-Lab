from ada.templates.selector import choose_variant


def test_variant_selection_high_score_short():
    assert choose_variant(85, '50-200') == 'short'


def test_variant_selection_mid_large_medium():
    assert choose_variant(60, '1000+') == 'medium'


def test_variant_selection_low_value():
    assert choose_variant(40, '50-200') == 'value'
