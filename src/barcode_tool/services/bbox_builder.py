"""Build export bbox geometry from recognized text bbox.

This module centralizes bbox policy so strategy/config tuning can happen in one place.
"""

from __future__ import annotations

from dataclasses import dataclass

from barcode_tool.models.types import BBox, DetectedLabel, ExportableLabel


@dataclass(frozen=True, slots=True)
class BBoxBuildConfig:
    """Configurable parameters for expanding text bbox into final label bbox."""

    x_padding: float = 12.0
    y_up_scale: float = 2.6
    y_down_scale: float = 0.15


DEFAULT_BBOX_CONFIG = BBoxBuildConfig()
BBOX_STRATEGIES: dict[str, BBoxBuildConfig] = {
    "default": DEFAULT_BBOX_CONFIG,
}


def compute_text_height(text_bbox: BBox) -> float:
    """Compute text bbox height; never returns negative value."""
    return max(text_bbox[3] - text_bbox[1], 0.0)


def expand_bbox(text_bbox: BBox, config: BBoxBuildConfig) -> BBox:
    """Expand text bbox according to strategy config (before page clamping)."""
    text_x0, text_y0, text_x1, text_y1 = text_bbox
    text_height = compute_text_height(text_bbox)

    return (
        text_x0 - config.x_padding,
        text_y0 - text_height * config.y_up_scale,
        text_x1 + config.x_padding,
        text_y1 + text_height * config.y_down_scale,
    )


def clamp_bbox_to_page(bbox: BBox, page_rect: BBox) -> BBox:
    """Clamp bbox into page rectangle and fix inverted coordinates."""
    x0, y0, x1, y1 = bbox
    page_x0, page_y0, page_x1, page_y1 = page_rect

    clamped_x0 = max(page_x0, x0)
    clamped_y0 = max(page_y0, y0)
    clamped_x1 = min(page_x1, x1)
    clamped_y1 = min(page_y1, y1)

    if clamped_x0 > clamped_x1:
        clamped_x0 = clamped_x1
    if clamped_y0 > clamped_y1:
        clamped_y0 = clamped_y1

    return (clamped_x0, clamped_y0, clamped_x1, clamped_y1)


def _resolve_bbox_config(strategy: str, config: BBoxBuildConfig | None = None) -> BBoxBuildConfig:
    if config is not None:
        return config
    if strategy not in BBOX_STRATEGIES:
        raise ValueError(f"Unsupported bbox strategy: {strategy}")
    return BBOX_STRATEGIES[strategy]


def build_label_bbox(
    text_bbox: BBox,
    page_rect: BBox,
    strategy: str = "default",
    config: BBoxBuildConfig | None = None,
) -> BBox:
    """Build final export label bbox from text bbox.

    Strategy is extensible for future templates. `config` overrides predefined strategy.
    """
    resolved = _resolve_bbox_config(strategy=strategy, config=config)
    expanded = expand_bbox(text_bbox=text_bbox, config=resolved)
    return clamp_bbox_to_page(expanded, page_rect=page_rect)


def build_exportable_label(
    detected_label: DetectedLabel,
    page_rect: BBox,
    strategy: str = "default",
    config: BBoxBuildConfig | None = None,
) -> ExportableLabel:
    """Convert one recognition result into an exportable record."""
    label_bbox = build_label_bbox(
        text_bbox=detected_label.text_bbox,
        page_rect=page_rect,
        strategy=strategy,
        config=config,
    )
    return ExportableLabel(
        page_index=detected_label.page_index,
        group_index=detected_label.group_index,
        candidate_filename=detected_label.candidate_filename,
        text_bbox=detected_label.text_bbox,
        label_bbox=label_bbox,
        first_line=detected_label.first_line,
        second_line=detected_label.second_line,
        third_line=detected_label.third_line,
    )
