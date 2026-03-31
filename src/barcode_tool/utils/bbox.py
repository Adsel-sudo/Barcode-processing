"""Bounding-box utility helpers."""

from __future__ import annotations

BBox = tuple[float, float, float, float]


def union_bbox(boxes: list[BBox]) -> BBox:
    """Return minimal bbox containing all input boxes."""
    if not boxes:
        return (0.0, 0.0, 0.0, 0.0)
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    return (x0, y0, x1, y1)
