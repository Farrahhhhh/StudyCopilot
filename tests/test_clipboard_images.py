import pytest
from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtGui import QImage
from studycopilot.capture.clipboard import clone_mime


def test_snapshot_preserves_image_html_urls_and_private_mime(qapp):
    original = QMimeData()
    image = QImage(12, 12, QImage.Format.Format_ARGB32)
    image.fill(0xFF336699)
    original.setImageData(image)
    original.setHtml("<b>test</b>")
    original.setUrls([QUrl("https://example.com/document")])
    original.setData("application/x-study-test", b"binary\x00data")
    copied = clone_mime(original)
    assert copied.hasImage() and copied.imageData().pixel(0, 0) == image.pixel(0, 0)
    assert copied.html() == original.html()
    assert copied.urls() == original.urls()
    assert bytes(copied.data("application/x-study-test")) == b"binary\x00data"
    with pytest.raises(ValueError):
        clone_mime(original, max_bytes=10)


def test_alias_case_variants_are_normalized(db):
    from studycopilot.knowledge.concepts import ConceptStore
    store = ConceptStore(db)
    concept = store.create("Transconductance", english_name="transconductance", aliases=("GM", "gm", " GM "))
    aliases = db.all("SELECT alias FROM concept_aliases WHERE concept_id=?", (concept["id"],))
    assert sorted(a["alias"] for a in aliases) == ["gm", "transconductance"]
