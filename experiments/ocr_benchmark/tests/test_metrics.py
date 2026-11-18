import pytest
from ocrbench.metrics import field_metrics, text_metrics, teds


def test_edit_rates_and_omission():
    m = text_metrics('a b c', 'a c')
    assert m['wer'] == pytest.approx(1/3)
    assert m['token_omission_rate'] == pytest.approx(1/3)
    assert m['token_precision'] == 1
    assert m['token_recall'] == pytest.approx(2/3)


def test_insertions_can_exceed_one():
    assert text_metrics('a', 'abcdef')['cer'] == 5
    assert text_metrics('', 'a')['cer'] is None
    assert text_metrics('', 'a')['characters']['insertions'] == 1


def test_unicode_and_numbers_not_silently_normalized():
    assert text_metrics('ș', 's\u0326')['cer'] == 0
    assert text_metrics('0.5 mg', '5 mg')['cer'] > 0
    assert text_metrics('7,8', '7.8')['cer'] > 0


def test_duplicate_tokens_and_wrong_fields():
    assert text_metrics('a a', 'a')['token_recall'] == .5
    assert field_metrics({'dose': '0.5'}, {'dose': '5'}) == {
        'tp': 0, 'fp': 1, 'fn': 1, 'precision': 0, 'recall': 0, 'f1': 0}


def test_teds_content_and_spans():
    a = '<table><tr><td>abc</td></tr></table>'
    b = '<table><tr><td>abd</td></tr></table>'
    assert teds(a, a) == 1
    assert teds(a, b) == pytest.approx(5/6)
    assert teds(a, b, True) == 1
    assert teds(a, '') == 0
    assert teds(a, '<table><tr><td colspan="2">abc</td></tr></table>', True) < 1
