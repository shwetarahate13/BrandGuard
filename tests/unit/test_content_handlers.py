"""Image-handler geometry and persisted brand-palette checks."""
from io import BytesIO
from types import SimpleNamespace

from PIL import Image, ImageDraw
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.models.models import Asset, AssetKind, GuidelineClause, GuidelineDoc
from backend.app.pipeline import content_handlers


def test_rapidocr_word_output_maps_offsets_and_boxes(monkeypatch):
    output = SimpleNamespace(word_results=(
        (
            ("Brand", 0.97, [[1, 2], [21, 2], [21, 10], [1, 10]]),
            ("Guard", 0.91, [[24, 2], [45, 2], [45, 10], [24, 10]]),
        ),
    ))
    monkeypatch.setattr(content_handlers, "_get_ocr_engine", lambda: lambda *_args, **_kwargs: output)
    monkeypatch.setattr(
        content_handlers,
        "get_settings",
        lambda: SimpleNamespace(OCR_BACKEND="rapidocr"),
    )

    text, regions = content_handlers._ocr(object())

    assert text == "Brand Guard"
    assert [region["start"] for region in regions] == [0, 6]
    assert [region["end"] for region in regions] == [5, 11]
    assert regions[0]["bbox"] == [1.0, 2.0, 21.0, 10.0]


def test_tesseract_word_output_maps_offsets_confidence_and_boxes(monkeypatch):
    import sys
    from types import SimpleNamespace

    output = {
        "text": ["Brand", "", "Guard"],
        "conf": ["96", "-1", "82"],
        "left": [1, 0, 24],
        "top": [2, 0, 2],
        "width": [20, 0, 21],
        "height": [8, 0, 8],
    }
    fake_tesseract = SimpleNamespace(
        Output=SimpleNamespace(DICT="dict"),
        image_to_data=lambda *_args, **_kwargs: output,
    )
    monkeypatch.setitem(sys.modules, "pytesseract", fake_tesseract)
    monkeypatch.setattr(
        content_handlers,
        "get_settings",
        lambda: SimpleNamespace(OCR_BACKEND="tesseract"),
    )

    text, regions = content_handlers._ocr(object())

    assert text == "Brand Guard"
    assert [region["start"] for region in regions] == [0, 6]
    assert [region["end"] for region in regions] == [5, 11]
    assert regions[0]["bbox"] == [1, 2, 21, 10]
    assert regions[1]["confidence"] == 0.82


def test_palette_check_uses_approved_asset_rgb_metadata(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    image = Image.new("RGB", (80, 60), (180, 20, 20))
    encoded = BytesIO()
    image.save(encoded, format="PNG")
    monkeypatch.setattr(
        content_handlers,
        "get_settings",
        lambda: SimpleNamespace(IMAGE_REVIEW_ENABLED=True, ASSET_STORAGE_DIR="/tmp/brandguard-assets"),
    )

    with Session(engine) as db:
        db.add(Asset(id="palette-asset", kind=AssetKind.image, name="Approved palette", metadata_={"colors": ["#000000"]}))
        db.commit()
        findings, sources = content_handlers.ImageContentHandler("image/png").inspect(encoded.getvalue(), None, db)

    assert len(findings) == 1
    assert findings[0]["source_id"] == "palette-asset"
    assert findings[0]["location"] == {"page": 1, "bbox": [0, 0, 80, 60], "media": "image"}
    assert sources[0]["id"] == "palette-asset"
    engine.dispose()


def test_image_handler_returns_actionable_message_when_disabled(monkeypatch):
    monkeypatch.setattr(
        content_handlers,
        "get_settings",
        lambda: SimpleNamespace(IMAGE_REVIEW_ENABLED=False),
    )

    try:
        content_handlers.ImageContentHandler("image/png").extract_content(b"unused")
    except ValueError as exc:
        assert "IMAGE_REVIEW_ENABLED" in str(exc)
    else:
        raise AssertionError("disabled image review should fail before decoding the upload")


def test_logo_clear_space_requires_readable_logo_and_measurable_guideline(monkeypatch, tmp_path):
    pytest.importorskip("cv2", reason="OpenCV is required for logo template matching")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    canvas = Image.new("RGB", (240, 160), "white")
    logo = Image.new("RGB", (32, 24), "white")
    draw = ImageDraw.Draw(logo)
    draw.rectangle((1, 1, 17, 22), fill=(14, 35, 28))
    draw.ellipse((19, 6, 30, 17), fill=(212, 163, 72))
    canvas.paste(logo, (10, 15))
    image_bytes = BytesIO()
    canvas.save(image_bytes, format="PNG")
    logo_path = tmp_path / "approved-logo.png"
    logo.save(logo_path, format="PNG")
    monkeypatch.setattr(
        content_handlers,
        "get_settings",
        lambda: SimpleNamespace(IMAGE_REVIEW_ENABLED=True, ASSET_STORAGE_DIR=str(tmp_path)),
    )

    with Session(engine) as db:
        doc = GuidelineDoc(id="logo-guideline", title="Logo rules")
        clause = GuidelineClause(
            id="logo-clause",
            doc_id=doc.id,
            title="Logo clear space",
            text="Leave generous clear space around the logo.",
        )
        db.add_all([
            doc,
            clause,
            Asset(id="approved-logo", kind=AssetKind.logo, name="Primary logo", file_path=str(logo_path)),
        ])
        db.commit()
        handler = content_handlers.ImageContentHandler("image/png")

        without_measurable_rule, _ = handler.inspect(image_bytes.getvalue(), {"regions": []}, db)
        clause.text = "Leave at least 20 px clear space around the logo."
        db.commit()
        with_measurable_rule, _ = handler.inspect(image_bytes.getvalue(), {"regions": []}, db)

    assert without_measurable_rule == []
    clearspace = next(finding for finding in with_measurable_rule if "clear space" in finding["issue"].lower())
    assert "at least 20px" in clearspace["issue"]
    assert clearspace["location"]["bbox"] == [10, 15, 42, 39]
    engine.dispose()


def test_readable_logo_without_opencv_skips_matching_without_breaking_image_review(monkeypatch, tmp_path):
    import builtins

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    image_bytes = BytesIO()
    Image.new("RGB", (64, 48), "white").save(image_bytes, format="PNG")
    logo_path = tmp_path / "approved-logo.png"
    Image.new("RGB", (16, 12), "black").save(logo_path, format="PNG")
    monkeypatch.setattr(
        content_handlers,
        "get_settings",
        lambda: SimpleNamespace(IMAGE_REVIEW_ENABLED=True, ASSET_STORAGE_DIR=str(tmp_path)),
    )
    original_import = builtins.__import__

    def reject_opencv(name, *args, **kwargs):
        if name == "cv2":
            raise ImportError("OpenCV is unavailable in the light install")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_opencv)
    with Session(engine) as db:
        db.add(Asset(id="readable-logo", kind=AssetKind.logo, name="Approved logo", file_path=str(logo_path)))
        db.commit()
        findings, sources = content_handlers.ImageContentHandler("image/png").inspect(
            image_bytes.getvalue(), {"regions": []}, db
        )

    assert findings == []
    assert sources == []
    engine.dispose()


def test_missing_approved_logo_skips_heavy_opencv_import(monkeypatch, tmp_path):
    import builtins

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    image_bytes = BytesIO()
    Image.new("RGB", (64, 48), "white").save(image_bytes, format="PNG")
    monkeypatch.setattr(
        content_handlers,
        "get_settings",
        lambda: SimpleNamespace(IMAGE_REVIEW_ENABLED=True, ASSET_STORAGE_DIR=str(tmp_path)),
    )
    original_import = builtins.__import__

    def reject_opencv(name, *args, **kwargs):
        if name == "cv2":
            raise AssertionError("OpenCV should stay unloaded without a readable approved logo")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_opencv)
    with Session(engine) as db:
        db.add(Asset(
            id="missing-logo",
            kind=AssetKind.logo,
            name="Missing logo file",
            file_path="missing-logo.png",
        ))
        db.commit()
        findings, sources = content_handlers.ImageContentHandler("image/png").inspect(
            image_bytes.getvalue(), {"regions": []}, db
        )

    assert findings == []
    assert sources == []
    engine.dispose()
