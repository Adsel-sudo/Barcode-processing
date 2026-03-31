"""Export layer interfaces (reserved for next stage)."""

from __future__ import annotations

from pathlib import Path

from barcode_tool.models.types import ExportTask


def compute_label_bbox_from_text_bbox(text_bbox: tuple[float, float, float, float], padding: tuple[float, float, float, float] = (8, 8, 8, 8)) -> tuple[float, float, float, float]:
    """Reserve interface: derive label bbox from text bbox and padding policy."""
    raise NotImplementedError


def export_label_jpg(task: ExportTask, output_dir: Path, size: tuple[int, int] = (600, 400), dpi: int = 300) -> Path:
    """Reserve interface: crop and export barcode+text area as fixed-size JPG."""
    raise NotImplementedError


def render_debug_preview(task: ExportTask, output_dir: Path) -> Path:
    """Reserve interface: render debug preview image with bbox overlays."""
    raise NotImplementedError
