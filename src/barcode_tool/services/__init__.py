"""Domain services (PDF parsing, block detection, enrich, crop/export)."""

from barcode_tool.services.bbox_builder import (
    BBOX_STRATEGIES,
    DEFAULT_BBOX_CONFIG,
    BBoxBuildConfig,
    build_exportable_label,
    build_label_bbox,
)
from barcode_tool.services.label_builder import (
    build_detected_labels_from_page,
    compute_label_bbox,
    compute_text_bbox,
    deduplicate_filename,
    sanitize_filename,
)
from barcode_tool.services.label_enricher import (
    build_exportable_labels,
    enrich_detected_labels,
    validate_detected_label,
)

__all__ = [
    "BBoxBuildConfig",
    "DEFAULT_BBOX_CONFIG",
    "BBOX_STRATEGIES",
    "build_label_bbox",
    "build_exportable_label",
    "build_detected_labels_from_page",
    "build_exportable_labels",
    "validate_detected_label",
    "enrich_detected_labels",
    "compute_text_bbox",
    "compute_label_bbox",
    "sanitize_filename",
    "deduplicate_filename",
]
