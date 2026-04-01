"""Package one pipeline run directory into zip archive."""

from __future__ import annotations

import shutil
from pathlib import Path



def pack_run_output_dir(run_output_dir: Path, archive_root: Path | None = None) -> Path:
    """Pack the entire run_output_dir into one zip file.

    Args:
        run_output_dir: directory containing images/report/debug for one task run.
        archive_root: optional directory to store archive file.

    Returns:
        Path to generated .zip file.
    """
    if not run_output_dir.exists() or not run_output_dir.is_dir():
        raise FileNotFoundError(f"run_output_dir not found: {run_output_dir}")

    target_root = archive_root or run_output_dir.parent
    target_root.mkdir(parents=True, exist_ok=True)

    zip_base = target_root / run_output_dir.name
    zip_file = shutil.make_archive(str(zip_base), "zip", root_dir=run_output_dir)
    return Path(zip_file)
