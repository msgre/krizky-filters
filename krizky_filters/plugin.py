"""krizky-filters plugin — in-browser filtering via progressive enhancement."""

import json
import shutil
from pathlib import Path, PurePosixPath

from jinja2 import ChoiceLoader, FileSystemLoader

from krizky.hooks import hookimpl
from krizky_filters.json_gen import generate_filter_json
from krizky_filters.values import fetch_filter_values

_PLUGIN_TEMPLATES = Path(__file__).parent / "templates"
_PLUGIN_ASSETS = Path(__file__).parent / "assets"

_RESERVED_FILTER_KEYS = {"fields"}


def _get_main_table(config: dict) -> str:
    tables = config["sources"].get("tables", {})
    return next(name for name, t in tables.items() if t.get("main"))


def _iter_dimensions(filters_cfg: dict):
    """Yield (dim_key, dim_cfg) skipping reserved keys."""
    for key, val in filters_cfg.items():
        if key not in _RESERVED_FILTER_KEYS:
            yield key, val


def _build_filter_config(page_cfg: dict, config: dict) -> dict:
    """Build the JS filter-config object for injection into the page."""
    site_cfg = config.get("site", {})
    filters_cfg = page_cfg.get("filters", {})
    page_path = page_cfg.get("path", "/index.html")
    stem = PurePosixPath(page_path.lstrip("/")).stem
    json_url = f"/jsons/{stem}-filter.json"

    dimensions: dict = {}
    for dim_key, dim_cfg in _iter_dimensions(filters_cfg):
        entry: dict = {
            "label": dim_cfg["label"],
            "type": dim_cfg.get("type", "multiselect"),
        }
        if dim_cfg.get("many"):
            entry["many"] = True
        dimensions[dim_key] = entry

    photos_base_url = config.get("sources", {}).get("photos", {}).get("base_url", "").rstrip("/")

    return {
        "jsonUrl": json_url,
        "basePath": page_cfg.get("path", "/index.html"),
        "photosBaseUrl": photos_base_url,
        "pageSize": page_cfg.get("paginate_by") or site_cfg.get("paginate_by") or 0,
        "gridSelector": "[data-filter-grid]",
        "window": site_cfg.get("pagination_window", 2),
        "boundary": site_cfg.get("pagination_boundary", 1),
        "dimensions": dimensions,
    }


class FilterPlugin:
    def __init__(self) -> None:
        self._assets_copied: set[str] = set()

    @hookimpl
    def prepare_jinja2_environment(self, env, config, config_dir):
        """Insert plugin templates into the Jinja2 loader chain."""
        if not isinstance(env.loader, ChoiceLoader):
            return
        loaders = env.loader.loaders
        already = any(
            isinstance(ldr, FileSystemLoader)
            and str(_PLUGIN_TEMPLATES) in ldr.searchpath
            for ldr in loaders
        )
        if not already:
            # After project templates, before built-in krizky templates.
            env.loader.loaders = (
                [loaders[0], FileSystemLoader(str(_PLUGIN_TEMPLATES))]
                + loaders[1:]
            )

    @hookimpl
    def extra_template_vars(self, config, config_dir, conn):
        """Compute page_filters: distinct dimension values per filter page."""
        main_table = _get_main_table(config)
        page_filters: dict = {}

        for page_name, page_cfg in config.get("site", {}).get("pages", {}).items():
            if "filters" not in page_cfg:
                continue
            filters_cfg = page_cfg["filters"]
            dims: dict = {}
            for dim_key, dim_cfg in _iter_dimensions(filters_cfg):
                dims[dim_key] = {
                    "label": dim_cfg["label"],
                    "type": dim_cfg.get("type", "multiselect"),
                    "many": dim_cfg.get("many", False),
                    "values": fetch_filter_values(conn, main_table, dim_key, dim_cfg),
                }
            # _card_template is consumed by _filter_card_template.html
            dims["_card_template"] = page_cfg.get("card_template")
            page_filters[page_name] = dims

        return {"page_filters": page_filters}

    @hookimpl
    def inject_head(self, page_cfg, config):
        """Return CSS link tag for pages with filters:."""
        if "filters" not in page_cfg:
            return None
        return '<link rel="stylesheet" href="/krizky-filters/filters.css">'

    @hookimpl
    def inject_body_end(self, page_cfg, config):
        """Return filter config JSON + JS script tag for pages with filters:."""
        if "filters" not in page_cfg:
            return None
        filter_cfg = _build_filter_config(page_cfg, config)
        config_json = json.dumps(filter_cfg, ensure_ascii=False)
        return (
            f'<script type="application/json" id="filter-config">{config_json}</script>\n'
            f'<script src="/krizky-filters/filters.js" defer></script>'
        )

    @hookimpl
    def after_page_written(self, page_cfg, html_path, output_dir, records, config):
        """Generate filter JSON and copy plugin assets."""
        if "filters" not in page_cfg:
            return
        self._copy_assets(output_dir)
        generate_filter_json(page_cfg, records, output_dir, html_path)

    def _copy_assets(self, output_dir: Path) -> None:
        key = str(output_dir)
        if key in self._assets_copied:
            return
        dst = output_dir / "krizky-filters"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(_PLUGIN_ASSETS / "krizky-filters", dst)
        self._assets_copied.add(key)


plugin = FilterPlugin()
