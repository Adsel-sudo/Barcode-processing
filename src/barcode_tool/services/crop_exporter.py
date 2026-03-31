"""Render and export barcode label crops from PDF pages."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import fitz
from PIL import Image

from barcode_tool.models.types import BBox, BarcodeLabel, LabelExportResult
from barcode_tool.utils.filename import sanitize_filename_component


def render_label_crop(page: fitz.Page, label_bbox: BBox, zoom: float = 2.0) -> Image.Image:
    """Render a cropped image from one PDF page using label_bbox.

    The crop uses `page.get_pixmap(clip=...)` and returns an RGB PIL image.
    """
    clip = fitz.Rect(*label_bbox)
    page_rect = page.rect
    clip = clip.intersect(page_rect)
    if clip.is_empty or clip.width <= 0 or clip.height <= 0:
        raise ValueError("label_bbox is outside page rect or empty after clipping")

    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, clip=clip, alpha=False)
    image_bytes = pix.tobytes("png")
    return Image.open(BytesIO(image_bytes)).convert("RGB")


def fit_image_to_canvas(
    image: Image.Image,
    target_width: int = 589,
    target_height: int = 386,
) -> Image.Image:
    """Fit image to fixed canvas with aspect-ratio resize and white padding."""
    if image.width <= 0 or image.height <= 0:
        raise ValueError("image must have a positive size")

    scale = min(target_width / image.width, target_height / image.height)
    resized_width = max(1, int(round(image.width * scale)))
    resized_height = max(1, int(round(image.height * scale)))

    resized = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (target_width, target_height), color=(255, 255, 255))

    offset_x = (target_width - resized_width) // 2
    offset_y = (target_height - resized_height) // 2
    canvas.paste(resized, (offset_x, offset_y))
    return canvas


def _build_unique_filename(candidate_filename: str, used_names: dict[str, int]) -> str:
    safe = sanitize_filename_component(candidate_filename) or "unnamed"
    count = used_names.get(safe, 0)
    used_names[safe] = count + 1
    if count == 0:
        return f"{safe}.jpg"
    return f"{safe}_{count}.jpg"


def export_label_to_jpg(
    page: fitz.Page,
    label: BarcodeLabel,
    output_dir: Path,
    used_names: dict[str, int],
    zoom: float = 2.0,
    target_width: int = 589,
    target_height: int = 386,
    jpeg_quality: int = 95,
) -> LabelExportResult:
    """Export one BarcodeLabel as fixed-size JPG without geometric distortion."""
    try:
        crop = render_label_crop(page=page, label_bbox=label.label_bbox, zoom=zoom)
        final_image = fit_image_to_canvas(
            image=crop,
            target_width=target_width,
            target_height=target_height,
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        filename = _build_unique_filename(label.candidate_filename, used_names)
        output_path = output_dir / filename
        final_image.save(output_path, format="JPEG", quality=jpeg_quality, dpi=(300, 300))

        return LabelExportResult(
            page_index=label.page_index,
            group_index=label.group_index,
            candidate_filename=label.candidate_filename,
            success=True,
            output_path=str(output_path),
        )
    except Exception as exc:  # noqa: BLE001 - keep batch export resilient per requirements
        return LabelExportResult(
            page_index=label.page_index,
            group_index=label.group_index,
            candidate_filename=label.candidate_filename,
            success=False,
            error_message=str(exc),
        )


def export_labels_from_pdf(
    pdf_path: Path,
    labels: list[BarcodeLabel],
    output_dir: Path,
    zoom: float = 2.0,
    target_width: int = 589,
    target_height: int = 386,
    jpeg_quality: int = 95,
) -> list[LabelExportResult]:
    """Export all labels from a PDF in batch; one failure won't stop others."""
    results: list[LabelExportResult] = []
    used_names: dict[str, int] = {}

    with fitz.open(pdf_path) as doc:
        for label in labels:
            if label.page_index < 0 or label.page_index >= len(doc):
                results.append(
                    LabelExportResult(
                        page_index=label.page_index,
                        group_index=label.group_index,
                        candidate_filename=label.candidate_filename,
                        success=False,
                        error_message=f"invalid page_index: {label.page_index}",
                    )
                )
                continue

            page = doc[label.page_index]
            one_result = export_label_to_jpg(
                page=page,
                label=label,
                output_dir=output_dir,
                used_names=used_names,
                zoom=zoom,
                target_width=target_width,
                target_height=target_height,
                jpeg_quality=jpeg_quality,
            )
            results.append(one_result)

    return results
