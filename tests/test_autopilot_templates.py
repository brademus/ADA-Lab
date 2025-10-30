from ada.templates import render as tmpl


def test_render_short_personalizes():
    subj, body = tmpl.render_template('short', {
        'first_name': 'Ava',
        'company': 'Base44',
        'value_prop': 'boost reply rates by 20%',
        'sender_name': 'ADA',
    })
    assert 'Ava' in body
    assert 'Base44' in subj or 'Base44' in body
    assert subj.strip() != ''
    assert body.strip() != ''
