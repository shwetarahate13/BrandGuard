"""Image extraction and visual brand checks for supported uploaded media."""
from __future__ import annotations

import io
import json
import logging
import re
import threading
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.models.models import Asset, AssetKind, GuidelineClause

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/svg+xml"}
MAX_IMAGE_PIXELS = 12_000_000
_OCR_ENGINE = None
_OCR_ENGINE_LOCK = threading.Lock()


def _open_image(contents: bytes, mime_type: str) -> Any:
    from PIL import Image

    if mime_type == "image/svg+xml":
        from defusedxml import ElementTree
        import cairosvg

        root = ElementTree.fromstring(contents)
        forbidden = {"script", "foreignObject", "image", "iframe", "audio", "video"}
        for element in root.iter():
            tag = element.tag.rsplit("}", 1)[-1]
            if tag in forbidden:
                raise ValueError("SVG contains unsupported active or external content")
            for key, value in element.attrib.items():
                if key.rsplit("}", 1)[-1] in {"href", "src"} and not value.startswith("#"):
                    raise ValueError("SVG external references are not supported")
                if re.search(r"url\((?!\s*['\"]?#)[^)]+\)", value, flags=re.I) or "@import" in value.lower():
                    raise ValueError("SVG external styles and resources are not supported")
            if element.text and ("@import" in element.text.lower() or re.search(r"url\((?!\s*['\"]?#)[^)]+\)", element.text, flags=re.I)):
                raise ValueError("SVG external styles and resources are not supported")
        view_box = [float(part) for part in re.split(r"[\s,]+", root.attrib.get("viewBox", "").strip()) if part]

        def svg_dimension(name: str, fallback: float) -> float:
            match = re.match(r"\s*(\d+(?:\.\d+)?)", root.attrib.get(name, ""))
            if match:
                return max(1.0, float(match.group(1)))
            return max(1.0, fallback)

        intrinsic_width = svg_dimension("width", view_box[2] if len(view_box) == 4 else 512)
        intrinsic_height = svg_dimension("height", view_box[3] if len(view_box) == 4 else 512)
        scale = min(1.0, 2048 / intrinsic_width, 2048 / intrinsic_height)
        output_width = max(1, int(round(intrinsic_width * scale)))
        output_height = max(1, int(round(intrinsic_height * scale)))
        png_bytes = cairosvg.svg2png(bytestring=contents, output_width=output_width, output_height=output_height)
        image = Image.open(io.BytesIO(png_bytes))
    else:
        image = Image.open(io.BytesIO(contents))
    if image.width < 1 or image.height < 1 or image.width * image.height > MAX_IMAGE_PIXELS:
        raise ValueError("Image dimensions exceed the supported limit")
    if image.mode in {"RGBA", "LA"}:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        return background.convert("RGB")
    return image.convert("RGB")


def _get_ocr_engine():
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        with _OCR_ENGINE_LOCK:
            if _OCR_ENGINE is None:
                from rapidocr import RapidOCR

                _OCR_ENGINE = RapidOCR(params={
                    "Global.use_cls": False,
                    "EngineConfig.onnxruntime.intra_op_num_threads": 1,
                    "EngineConfig.onnxruntime.inter_op_num_threads": 1,
                    "EngineConfig.onnxruntime.enable_cpu_mem_arena": False,
                })
    return _OCR_ENGINE


def _box_bounds(box: Any) -> list[float] | None:
    points = box.tolist() if hasattr(box, "tolist") else box
    if not isinstance(points, (list, tuple)):
        return None
    if len(points) == 4 and all(isinstance(value, (int, float)) for value in points):
        x0, y0, x1, y1 = (float(value) for value in points)
        return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
    coordinates = []
    for point in points:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            try:
                coordinates.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError):
                continue
    if not coordinates:
        return None
    xs, ys = zip(*coordinates)
    return [min(xs), min(ys), max(xs), max(ys)]


def _sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    return list(value)


def _ocr(image: Any) -> tuple[str, list[dict[str, Any]]]:
    try:
        result = _get_ocr_engine()(image, return_word_box=True)
    except Exception as exc:
        logger.exception("Image OCR failed")
        raise ValueError("Unable to read text from image; the RapidOCR runtime could not process it") from exc

    pieces: list[str] = []
    regions: list[dict[str, Any]] = []
    offset = 0
    word_lines = _sequence(getattr(result, "word_results", None))
    words = [word for line in word_lines for word in line]
    if not words:
        boxes = _sequence(getattr(result, "boxes", None))
        texts = _sequence(getattr(result, "txts", None))
        scores = _sequence(getattr(result, "scores", None))
        words = list(zip(texts, scores, boxes))
    for word_data in words:
        if len(word_data) != 3:
            continue
        value, raw_confidence, box = word_data
        word = str(value).strip()
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            confidence = 0
        if not word or confidence < 0.35:
            continue
        bbox = _box_bounds(box)
        if bbox is None:
            continue
        if pieces:
            pieces.append(" ")
            offset += 1
        start = offset
        pieces.append(word)
        offset += len(word)
        regions.append({
            "start": start,
            "end": offset,
            "bbox": [round(value, 2) for value in bbox],
            "confidence": confidence,
        })
    return "".join(pieces), regions


def _rgb_color(value: Any) -> tuple[int, int, int] | None:
    if isinstance(value, str):
        match = re.fullmatch(r"#?([0-9a-fA-F]{6})", value.strip())
        if match:
            raw = match.group(1)
            return tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4))
        match = re.fullmatch(r"rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)", value.strip(), re.I)
        if match:
            rgb = tuple(int(match.group(i)) for i in (1, 2, 3))
            return rgb if all(0 <= c <= 255 for c in rgb) else None
    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            rgb = tuple(int(c) for c in value)
            return rgb if all(0 <= c <= 255 for c in rgb) else None
        except (TypeError, ValueError):
            return None
    return None


def _collect_colors(value: Any) -> list[tuple[int, int, int]]:
    if isinstance(value, dict):
        return [color for nested in value.values() for color in _collect_colors(nested)]
    color = _rgb_color(value)
    if color:
        return [color]
    if isinstance(value, (list, tuple)):
        return [color for item in value for color in _collect_colors(item)]
    return []


def _asset_path(asset: Asset) -> Path | None:
    if not asset.file_path:
        return None
    path = Path(asset.file_path)
    allowed_roots = [Path(get_settings().ASSET_STORAGE_DIR), Path(__file__).resolve().parents[1] / "static"]
    for root in allowed_roots:
        resolved_root = root.resolve()
        candidates = [path] if path.is_absolute() else [resolved_root / path, resolved_root / path.name]
        if path.is_absolute():
            candidates.append(resolved_root / Path(*path.parts[1:]))
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
                resolved.relative_to(resolved_root)
                if resolved.is_file():
                    return resolved
            except (OSError, ValueError):
                continue
    return None


def _guideline_clause(clauses: list[GuidelineClause], terms: tuple[str, ...]) -> GuidelineClause | None:
    return next((clause for clause in clauses if any(term in (clause.title or "").lower() + " " + clause.text.lower() for term in terms)), None)


def _source_quote(text: str) -> str:
    return text[:500]


def _minimum_clearspace(text: str, logo_width: int, logo_height: int) -> float:
    requirements = [
        float(value) * logo_height
        for value in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:x|times)\b", text.lower())
    ]
    requirements.extend(
        float(value)
        for value in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:px|pixels?)\b", text.lower())
    )
    requirements.extend(
        float(value) * logo_height / 100
        for value in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)\s*%(?!\s+of\s+(?:the\s+)?(?:logo\s+)?width\b)", text, flags=re.I)
    )
    requirements.extend(
        float(value) * logo_width / 100
        for value in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)\s*%\s+of\s+(?:the\s+)?(?:logo\s+)?width\b", text.lower())
    )
    if re.search(r"\b(?:half|one[- ]half)\s+(?:of\s+)?(?:the\s+)?(?:logo\s+)?height\b", text.lower()):
        requirements.append(logo_height / 2)
    if re.search(r"\b(?:one|1)\s+(?:logo\s+)?height\b", text.lower()):
        requirements.append(float(logo_height))
    if re.search(r"\b(?:equal|equivalent)\s+to\s+(?:the\s+)?(?:logo\s+)?height\b", text.lower()):
        requirements.append(float(logo_height))
    # Some brand guides define the clear area as a fraction of logo width.
    if re.search(r"\b(?:half|one[- ]half)\s+(?:of\s+)?(?:the\s+)?(?:logo\s+)?width\b", text.lower()):
        requirements.append(logo_width / 2)
    return max(requirements, default=0.0)


class ImageContentHandler:
    def __init__(self, mime_type: str):
        self.mime_type = mime_type

    def extract_content(self, contents: bytes) -> tuple[str, dict[str, Any]]:
        try:
            if not get_settings().IMAGE_REVIEW_ENABLED:
                raise ValueError("Image review is disabled on this instance; enable IMAGE_REVIEW_ENABLED on a larger-memory instance")
            image = _open_image(contents, self.mime_type)
            text, regions = _ocr(image)
            return text, {"media": "image", "width": image.width, "height": image.height, "regions": regions}
        except ValueError:
            raise
        except Exception as exc:
            logger.exception("Image extraction failed")
            raise ValueError("Failed to process uploaded image") from exc

    def inspect(self, contents: bytes, layout: dict[str, Any] | None, db: Session) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if not get_settings().IMAGE_REVIEW_ENABLED:
            raise ValueError("Image review is disabled on this instance")
        import numpy as np
        from PIL import Image

        image = _open_image(contents, self.mime_type)
        pixels = np.asarray(image)
        height, width = pixels.shape[:2]
        assets = db.query(Asset).all()
        clauses = db.query(GuidelineClause).all()
        findings: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []

        def add_source(source_type: str, source_id: str, title: str, text: str) -> None:
            if not any(str(source.get("id")) == source_id for source in sources):
                sources.append({"id": source_id, "type": source_type, "title": title, "text": text, "similarity": 1.0})

        # Compare dominant image colors against real palette values in approved asset metadata.
        palette_assets = []
        for asset in assets:
            colors = _collect_colors(asset.metadata_ or {})
            if colors:
                palette_assets.append((asset, colors))
        if palette_assets:
            quantized = image.quantize(colors=8, method=Image.Quantize.MEDIANCUT).convert("RGB")
            dominant = [color for _, color in quantized.getcolors(maxcolors=width * height) or []]
            approved = [(asset, color) for asset, colors in palette_assets for color in colors]
            mismatch = next((tuple(color) for color in dominant if not any(all(abs(int(color[i]) - approved_color[i]) <= 15 for i in range(3)) for _, approved_color in approved)), None)
            if mismatch:
                asset = palette_assets[0][0]
                source_text = f"{asset.name} {json.dumps(asset.metadata_ or {}, sort_keys=True)}"
                add_source("asset", str(asset.id), asset.name, source_text)
                findings.append({
                    "span_start": None, "span_end": None, "category": "messaging",
                    "issue": f"Dominant image color RGB{mismatch} falls outside the approved brand palette tolerance of ±15 per channel.",
                    "source_type": "asset", "source_id": str(asset.id), "source_quote": asset.name,
                    "severity": "major", "confidence": "high", "needs_human": True,
                    "location": {"page": 1, "bbox": [0, 0, width, height], "media": "image"},
                })

        # Compare the approved logo template with the submitted image using normalized correlation.
        logo_assets = db.query(Asset).filter(Asset.kind == AssetKind.logo).all()
        if logo_assets:
            import cv2

            search_scale = min(1.0, 1600 / max(width, height))
            search_pixels = cv2.resize(pixels, None, fx=search_scale, fy=search_scale, interpolation=cv2.INTER_AREA) if search_scale < 1 else pixels
            haystack = cv2.cvtColor(search_pixels, cv2.COLOR_RGB2GRAY)
            best_match = None
            for asset in logo_assets:
                asset_path = _asset_path(asset)
                if asset_path is None:
                    continue
                try:
                    template_image = _open_image(asset_path.read_bytes(), "image/svg+xml" if asset_path.suffix.lower() == ".svg" else "image/jpeg" if asset_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png")
                    template = cv2.cvtColor(np.asarray(template_image), cv2.COLOR_RGB2GRAY)
                    if search_scale < 1:
                        template = cv2.resize(template, None, fx=search_scale, fy=search_scale, interpolation=cv2.INTER_AREA)
                    if template.shape[0] < 2 or template.shape[1] < 2:
                        continue
                    for template_scale in (0.5, 0.75, 1.0, 1.25, 1.5):
                        candidate = cv2.resize(template, None, fx=template_scale, fy=template_scale, interpolation=cv2.INTER_AREA)
                        if candidate.shape[0] < 2 or candidate.shape[1] < 2 or candidate.shape[0] > haystack.shape[0] or candidate.shape[1] > haystack.shape[1]:
                            continue
                        match = cv2.matchTemplate(haystack, candidate, cv2.TM_CCOEFF_NORMED)
                        _, score, _, location = cv2.minMaxLoc(match)
                        if best_match is None or score > best_match[0]:
                            inv_scale = 1 / search_scale
                            best_match = (
                                score,
                                (int(round(location[0] * inv_scale)), int(round(location[1] * inv_scale))),
                                int(round(candidate.shape[1] * inv_scale)),
                                int(round(candidate.shape[0] * inv_scale)),
                            )
                except Exception:
                    logger.exception("Approved logo asset could not be matched")
            if best_match and best_match[0] >= 0.72:
                _, (x, y), logo_width, logo_height = best_match
                clearspace_clause = _guideline_clause(clauses, ("clear space", "clearspace", "minimum space", "logo spacing"))
                if clearspace_clause:
                    minimum = _minimum_clearspace(clearspace_clause.text, logo_width, logo_height)
                    clear_space = min(x, y, width - (x + logo_width), height - (y + logo_height))
                    for region in (layout or {}).get("regions", []):
                        text_box = [int(round(float(value))) for value in region.get("bbox", [0, 0, 0, 0])]
                        if len(text_box) != 4:
                            continue
                        tx0, ty0, tx1, ty1 = text_box
                        if tx0 >= x and ty0 >= y and tx1 <= x + logo_width and ty1 <= y + logo_height:
                            continue
                        dx = max(x - tx1, tx0 - (x + logo_width), 0)
                        dy = max(y - ty1, ty0 - (y + logo_height), 0)
                        clear_space = min(clear_space, float((dx * dx + dy * dy) ** 0.5))
                    if minimum > 0 and clear_space < minimum:
                        add_source("guideline_clause", clearspace_clause.id, clearspace_clause.title or clearspace_clause.code or "Logo clear-space guideline", clearspace_clause.text)
                        findings.append({
                            "span_start": None, "span_end": None, "category": "messaging",
                            "issue": f"Logo clear space is {clear_space:.0f}px; the guideline requires at least {minimum:.0f}px.",
                            "source_type": "guideline_clause", "source_id": clearspace_clause.id,
                            "source_quote": _source_quote(clearspace_clause.text), "severity": "major", "confidence": "high",
                            "needs_human": True, "location": {"page": 1, "bbox": [x, y, x + logo_width, y + logo_height], "media": "image"},
                        })

        # Check text OCR regions against a local background estimate for WCAG AA contrast.
        layout = layout or {}
        regions = layout.get("regions", [])
        accessibility_clause = _guideline_clause(clauses, ("accessib", "contrast", "readab"))
        if accessibility_clause and regions:
            add_source("guideline_clause", accessibility_clause.id, accessibility_clause.title or accessibility_clause.code or "Accessibility guideline", accessibility_clause.text)
            for region in regions:
                x0, y0, x1, y1 = [int(round(float(v))) for v in region.get("bbox", [0, 0, 0, 0])]
                x0 = max(0, min(width, x0)); x1 = max(0, min(width, x1))
                y0 = max(0, min(height, y0)); y1 = max(0, min(height, y1))
                if x1 <= x0 or y1 <= y0:
                    continue
                pad = max(2, min(8, (y1 - y0) // 3))
                patch = pixels[max(0, y0 - pad):min(height, y1 + pad), max(0, x0 - pad):min(width, x1 + pad)]
                if patch.size == 0:
                    continue
                border = np.concatenate((patch[0, :, :], patch[-1, :, :], patch[:, 0, :], patch[:, -1, :]), axis=0)
                bg = np.median(border, axis=0)
                inner = pixels[y0:y1, x0:x1].reshape(-1, 3).astype(float)
                distance = np.max(np.abs(inner - bg), axis=1)
                text_pixels = inner[distance >= 35]
                if len(text_pixels) < 3:
                    continue
                fg = np.median(text_pixels, axis=0)

                def luminance(rgb):
                    normalized = np.asarray(rgb, dtype=float) / 255.0
                    linear = np.where(normalized <= 0.04045, normalized / 12.92, ((normalized + 0.055) / 1.055) ** 2.4)
                    return float(np.dot(linear, [0.2126, 0.7152, 0.0722]))

                bg_lum, fg_lum = luminance(bg), luminance(fg)
                ratio = (max(bg_lum, fg_lum) + 0.05) / (min(bg_lum, fg_lum) + 0.05)
                threshold = 3.0 if y1 - y0 >= 24 else 4.5
                if ratio < threshold:
                    findings.append({
                        "span_start": region.get("start"), "span_end": region.get("end"), "category": "accessibility",
                        "issue": f"Detected text contrast ratio {ratio:.2f}:1 is below the WCAG AA {threshold:.1f}:1 threshold.",
                        "source_type": "guideline_clause", "source_id": accessibility_clause.id,
                        "source_quote": _source_quote(accessibility_clause.text), "severity": "major", "confidence": "medium",
                        "needs_human": True, "location": {"page": 1, "bbox": [x0, y0, x1, y1], "media": "image"},
                    })
        return findings, sources


_HANDLERS = {mime: ImageContentHandler(mime) for mime in SUPPORTED_IMAGE_MIMES}


def get_content_handler(mime_type: str) -> ImageContentHandler | None:
    return _HANDLERS.get(mime_type)
