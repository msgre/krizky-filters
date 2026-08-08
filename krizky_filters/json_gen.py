"""Generate the compact filter JSON sidecar file."""

import json
from pathlib import Path, PurePosixPath


def generate_filter_json(
    page_cfg: dict,
    records: list[dict],
    output_dir: Path,
    html_path: str,
) -> None:
    """Write filter JSON to output_dir/jsons/{stem}-filter.json.

    Fields are controlled by filters.fields in page_cfg; if absent, all
    record fields are included.
    """
    fields: list[str] | None = page_cfg.get("filters", {}).get("fields")
    stem = PurePosixPath(html_path.lstrip("/")).stem
    json_dir = output_dir / "jsons"
    json_dir.mkdir(parents=True, exist_ok=True)

    data = (
        [{k: r.get(k) for k in fields} for r in records]
        if fields
        else list(records)
    )

    (json_dir / f"{stem}-filter.json").write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
