"""Render and export barcode label crops from PDF pages."""

from __future__ import annotations

from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

from barcode_tool.models.types import BBox, ExportableLabel, LabelExportResult
from barcode_tool.utils.filename import sanitize_filename_component


def render_label_crop(page: fitz.Page, label_bbox: BBox, render_dpi: int = 300) -> Image.Image:
    """Render a cropped image from one PDF page using label_bbox.

    The crop uses `page.get_pixmap(clip=...)` and returns an RGB PIL image.
    """
    clip = fitz.Rect(*label_bbox)
    page_rect = page.rect
    clip = clip.intersect(page_rect)
    if clip.is_empty or clip.width <= 0 or clip.height <= 0:
        raise ValueError("label_bbox is outside page rect or empty after clipping")

    pix = page.get_pixmap(dpi=render_dpi, clip=clip, alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def fit_image_to_canvas(
    image: Image.Image,
    target_width: int = 589,
    target_height: int = 386,
    footer_text: str = "Made in China",
    footer_height: int | None = None,
    main_scale_ratio: float = 0.93,
    footer_font_size: int = 42,
) -> Image.Image:
    """Fit image to fixed canvas, reserve footer area, and draw centered footer text."""
    if image.width <= 0 or image.height <= 0:
        raise ValueError("image must have a positive size")
    if target_width <= 0 or target_height <= 0:
        raise ValueError("target canvas size must be positive")

    reserved_footer = footer_height if footer_height is not None else max(88, int(round(target_height * 0.24)))
    reserved_footer = min(max(72, reserved_footer), target_height - 20)
    content_height = target_height - reserved_footer

    scale = min(target_width / image.width, content_height / image.height) * max(0.1, main_scale_ratio)
    resized_width = max(1, int(round(image.width * scale)))
    resized_height = max(1, int(round(image.height * scale)))

    resized = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (target_width, target_height), color=(255, 255, 255))

    offset_x = (target_width - resized_width) // 2
    offset_y = max(0, (content_height - resized_height) // 2)
    canvas.paste(resized, (offset_x, offset_y))

    draw = ImageDraw.Draw(canvas)
    font = _build_footer_font(
        draw=draw,
        footer_text=footer_text,
        target_width=target_width,
        reserved_footer=reserved_footer,
        footer_font_size=footer_font_size,
    )

    text_bbox = draw.textbbox((0, 0), footer_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = (target_width - text_width) // 2
    centered_text_y = content_height + max(0, (reserved_footer - text_height) // 2)
    upward_offset = max(10, reserved_footer // 6)
    min_bottom_margin = 14
    text_y = max(content_height, centered_text_y - upward_offset)
    text_y = min(text_y, target_height - text_height - min_bottom_margin)
    draw.text((text_x, text_y), footer_text, fill=(0, 0, 0), font=font)
    return canvas


def _build_footer_font(
    draw: ImageDraw.ImageDraw,
    footer_text: str,
    target_width: int,
    reserved_footer: int,
    footer_font_size: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Pick a footer font size that stays readable and visually balanced."""
    horizontal_padding = 20
    vertical_padding = 8
    max_text_width = max(10, target_width - horizontal_padding * 2)
    max_text_height = max(10, reserved_footer - vertical_padding * 2)

    try:
        default_size = max(34, footer_font_size)
        min_font_size = 26
        candidate_size = default_size
        while candidate_size >= min_font_size:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", candidate_size)
            text_bbox = draw.textbbox((0, 0), footer_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            if text_width <= max_text_width and text_height <= max_text_height:
                return font
            candidate_size -= 1
        return ImageFont.truetype("DejaVuSans-Bold.ttf", default_size)
    except OSError:
        return ImageFont.load_default()


def _build_unique_filename(candidate_filename: str, used_names: dict[str, int]) -> str:
    safe = sanitize_filename_component(candidate_filename) or "unnamed"
    count = used_names.get(safe, 0)
    used_names[safe] = count + 1
    if count == 0:
        return f"{safe}.jpg"
    return f"{safe}_{count}.jpg"


def export_label_to_jpg(
    page: fitz.Page,
    label: ExportableLabel,
    output_dir: Path,
    used_names: dict[str, int],
    render_dpi: int = 300,
    target_width: int = 589,
    target_height: int = 386,
    jpeg_quality: int = 95,
) -> LabelExportResult:
    """Export one ExportableLabel as fixed-size JPG without geometric distortion."""
    try:
        crop = render_label_crop(page=page, label_bbox=label.label_bbox, render_dpi=render_dpi)
        final_image = fit_image_to_canvas(
            image=crop,
            target_width=target_width,
            target_height=target_height,
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        filename = _build_unique_filename(label.candidate_filename, used_names)
        output_path = output_dir / filename
        final_image.save(
            output_path,
            format="JPEG",
            quality=jpeg_quality,
            subsampling=0,
            dpi=(render_dpi, render_dpi),
        )

        return LabelExportResult(
            page_index=label.page_index,
            group_index=label.group_index,
            candidate_filename=label.candidate_filename,
            success=True,
            label_bbox=label.label_bbox,
            output_path=str(output_path),
        )
    except Exception as exc:  # noqa: BLE001 - keep batch export resilient per requirements
        return LabelExportResult(
            page_index=label.page_index,
            group_index=label.group_index,
            candidate_filename=label.candidate_filename,
            success=False,
            label_bbox=label.label_bbox,
            error_message=str(exc),
        )


def export_labels_from_pdf(
    pdf_path: Path,
    labels: list[ExportableLabel],
    output_dir: Path,
    render_dpi: int = 300,
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
                        label_bbox=label.label_bbox,
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
                render_dpi=render_dpi,
                target_width=target_width,
                target_height=target_height,
                jpeg_quality=jpeg_quality,
            )
            results.append(one_result)

    return results
