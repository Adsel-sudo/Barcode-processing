"""Debug preview rendering for label bbox verification."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

from barcode_tool.models.types import BarcodeLabel


def render_page_preview(page: fitz.Page, zoom: float = 2.0) -> Image.Image:
    """Render a full PDF page into a PIL image for visual debugging."""
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")


def _load_debug_font() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Try loading a readable truetype font; fallback to Pillow default font."""
    try:
        return ImageFont.truetype("DejaVuSans.ttf", 14)
    except OSError:
        return ImageFont.load_default()


def draw_label_bboxes(
    image: Image.Image,
    labels: list[BarcodeLabel],
    zoom: float = 2.0,
    rect_color: tuple[int, int, int] = (255, 0, 0),
    text_color: tuple[int, int, int] = (0, 0, 255),
    rect_width: int = 2,
) -> Image.Image:
    """Draw label_bbox rectangles and candidate filenames on one page image."""
    draw = ImageDraw.Draw(image)
    font = _load_debug_font()

    for label in labels:
        x0, y0, x1, y1 = label.label_bbox
        rect = (x0 * zoom, y0 * zoom, x1 * zoom, y1 * zoom)
        draw.rectangle(rect, outline=rect_color, width=rect_width)

        text_x = rect[0]
        text_y = max(0, rect[1] - 16)
        draw.text((text_x, text_y), label.candidate_filename, fill=text_color, font=font)

    return image


def export_debug_previews(
    pdf_path: Path,
    labels: list[BarcodeLabel],
    output_dir: Path,
    zoom: float = 2.0,
) -> list[Path]:
    """Export multi-page debug previews with bbox overlays to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    labels_by_page: dict[int, list[BarcodeLabel]] = {}
    for label in labels:
        labels_by_page.setdefault(label.page_index, []).append(label)

    preview_paths: list[Path] = []
    with fitz.open(pdf_path) as doc:
        for page_index, page_labels in sorted(labels_by_page.items()):
            if page_index < 0 or page_index >= len(doc):
                continue

            image = render_page_preview(doc[page_index], zoom=zoom)
            draw_label_bboxes(image=image, labels=page_labels, zoom=zoom)

            out_path = output_dir / f"page_{page_index + 1:03d}_debug.jpg"
            image.save(out_path, format="JPEG", quality=90)
            preview_paths.append(out_path)

    return preview_paths


# Backward-compatible alias for earlier pipeline usage.
render_debug_previews = export_debug_previews
