import pytest
import pypdfium2 as pdfium
from render_pdf import render


def test_pdf_preparation_is_bounded_and_hashed(tmp_path):
    source = tmp_path/'sample.pdf'
    document = pdfium.PdfDocument.new()
    page = document.new_page(200, 300)
    document.save(source)
    page.close()
    document.close()
    result = render(source, tmp_path/'pages', dpi=72)
    assert len(result['pages']) == 1
    assert (tmp_path/'pages'/'page-0001.png').is_file()
    assert len(result['source_sha256']) == 64
    with pytest.raises(ValueError, match='pixel limit'):
        render(source, tmp_path/'oversized', max_pixels=1)
