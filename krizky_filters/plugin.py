"""krizky-filters plugin — in-browser filtering via progressive enhancement."""

import json
import logging
from pathlib import Path, PurePosixPath

from krizky.hooks import hookimpl
from krizky.plugin_helpers import register_plugin_templates, replace_tree
from krizky.render import render_config_str

from krizky_filters.json_gen import generate_filter_json
from krizky_filters.values import _parse_sort, fetch_filter_values

_log = logging.getLogger(__name__)

_DIM_TYPES = ("select", "multiselect", "text", "range")
_FACETS_MODES = ("hide", "disable")
_RANGE_IGNORED_KEYS = ("many", "sort", "search_fields")
_RANGE_DEFAULT_STEP = "any"
_SORT_DEFAULT_PARAM = "sort"
_SORT_DEFAULT_LABEL = "Výchozí řazení"

_PLUGIN_TEMPLATES = Path(__file__).parent / "templates"
_PLUGIN_ASSETS = Path(__file__).parent / "assets"


def _get_main_table(config: dict) -> str:
    tables = config["sources"].get("tables", {})
    return next(name for name, t in tables.items() if t.get("main"))


def _iter_dimensions(filters_cfg: dict):
    """Yield (dim_key, dim_cfg) from filters.dimensions."""
    yield from filters_cfg.get("dimensions", {}).items()


def _sort_spec_valid(spec) -> bool:
    """Return True if ``spec`` is a sort spec accepted by the value sorter.

    ``None`` is valid: the build treats it as the default ``count``.
    """
    if spec is None:
        return True
    if not isinstance(spec, str):
        return False
    try:
        _parse_sort(spec)
    except ValueError:
        return False
    return True


def _sort_is_valid(sort) -> bool:
    """Return True if ``sort`` is a valid string or ``{order, fallback}`` dict."""
    if isinstance(sort, dict):
        return "order" in sort and _sort_spec_valid(sort.get("fallback", "count"))
    return _sort_spec_valid(sort)


def _step_valid(step) -> bool:
    """Return True if ``step`` is ``"any"`` or a positive number (not a bool)."""
    if step == _RANGE_DEFAULT_STEP:
        return True
    return isinstance(step, (int, float)) and not isinstance(step, bool) and step > 0


def _range_params(dim_cfg: dict) -> tuple[str, int | float | str]:
    """Return ``(unit, step)`` of a range dimension, with defaults for invalid values."""
    unit = dim_cfg.get("unit", "")
    if not isinstance(unit, str):
        unit = ""
    step = dim_cfg.get("step", _RANGE_DEFAULT_STEP)
    if not _step_valid(step):
        step = _RANGE_DEFAULT_STEP
    return unit, step


def _sort_records_params(sort_cfg: dict) -> dict:
    """Normalize a ``sort_records`` config to ``{param, default_label, options}``.

    Options without ``field`` or ``label`` are dropped.
    """
    options = sort_cfg.get("options")
    if not isinstance(options, list):
        options = []
    return {
        "param": sort_cfg.get("param", _SORT_DEFAULT_PARAM),
        "default_label": sort_cfg.get("default_label", _SORT_DEFAULT_LABEL),
        "options": [
            {"field": o["field"], "label": o["label"]}
            for o in options
            if isinstance(o, dict) and o.get("field") and o.get("label")
        ],
    }


def _warn_invalid_sort_records(page_name: str, filters_cfg: dict) -> None:
    """Log a warning for each problem in the page's ``sort_records`` config."""
    sort_cfg = filters_cfg.get("sort_records")
    if sort_cfg is None:
        return
    if not isinstance(sort_cfg, dict):
        sort_cfg = {}
    param = sort_cfg.get("param", _SORT_DEFAULT_PARAM)
    if param in filters_cfg.get("dimensions", {}):
        _log.warning(
            "Filters on page '%s': sort_records param '%s' collides with a dimension key",
            page_name,
            param,
        )
    options = sort_cfg.get("options")
    if not options or not isinstance(options, list):
        _log.warning(
            "Filters on page '%s': sort_records has no options; the select will be empty",
            page_name,
        )
        return
    fields = filters_cfg.get("fields")
    for i, option in enumerate(options):
        option = option if isinstance(option, dict) else {}
        for key in ("field", "label"):
            if not option.get(key):
                _log.warning(
                    "Filters on page '%s': sort_records option #%d has no %s; it is ignored",
                    page_name,
                    i + 1,
                    key,
                )
        field = option.get("field")
        if field and fields and field not in fields:
            _log.warning(
                "Filters on page '%s': sort_records field '%s' is not in filters.fields; "
                "the field will be missing from the JSON",
                page_name,
                field,
            )


def _warn_invalid_filters(page_name: str, filters_cfg: dict) -> None:
    """Log a warning for each misconfiguration found in a page's ``filters`` config.

    Args:
        page_name: Key of the page in ``site.pages``.
        filters_cfg: The page's ``filters`` config.
    """
    dimensions = filters_cfg.get("dimensions")
    if not dimensions:
        _log.warning(
            "Filters on page '%s': no dimensions are configured; filters will not work",
            page_name,
        )
    facets_mode = filters_cfg.get("facets_mode")
    if facets_mode is not None and facets_mode not in _FACETS_MODES:
        _log.warning(
            "Filters on page '%s': unknown facets_mode '%s'; expected hide or disable",
            page_name,
            facets_mode,
        )
    for dim_key, dim_cfg in _iter_dimensions(filters_cfg):
        dim_type = dim_cfg.get("type", "multiselect")
        if dim_type not in _DIM_TYPES:
            _log.warning(
                "Filters on page '%s': dimension '%s' has unknown type '%s'; "
                "expected select, multiselect, text or range",
                page_name,
                dim_key,
                dim_type,
            )
        elif dim_type == "range":
            for key in _RANGE_IGNORED_KEYS:
                if key in dim_cfg:
                    _log.warning(
                        "Filters on page '%s': range dimension '%s' ignores key '%s'",
                        page_name,
                        dim_key,
                        key,
                    )
            if "step" in dim_cfg and not _step_valid(dim_cfg["step"]):
                _log.warning(
                    "Filters on page '%s': range dimension '%s' has invalid step '%s'; "
                    "expected a positive number or 'any'; using 'any'",
                    page_name,
                    dim_key,
                    dim_cfg["step"],
                )
            if "unit" in dim_cfg and not isinstance(dim_cfg["unit"], str):
                _log.warning(
                    "Filters on page '%s': range dimension '%s' has invalid unit '%s'; "
                    "expected a string; using empty unit",
                    page_name,
                    dim_key,
                    dim_cfg["unit"],
                )
        elif dim_type == "text":
            if not dim_cfg.get("search_fields"):
                _log.warning(
                    "Filters on page '%s': text dimension '%s' has no search_fields; "
                    "search will find nothing",
                    page_name,
                    dim_key,
                )
        elif "sort" in dim_cfg and not _sort_is_valid(dim_cfg["sort"]):
            _log.warning(
                "Filters on page '%s': dimension '%s' has invalid sort '%s'; "
                "expected count, alpha, columns like '-count,alpha' "
                "or {order: [...], fallback: ...}",
                page_name,
                dim_key,
                dim_cfg["sort"],
            )
    _warn_invalid_sort_records(page_name, filters_cfg)


def _resolve_url_template(config: dict, dim_key: str, dim_cfg: dict) -> str:
    """Resolve the URL template for a dimension.

    Priority:
      1. explicit `url` in dimension config
      2. auto-detect from matching category page (same `category` and `many`)
      3. empty string (no href)
    """
    explicit = dim_cfg.get("url")
    if explicit:
        return explicit

    many = bool(dim_cfg.get("many", False))
    for page_cfg in config.get("site", {}).get("pages", {}).values():
        if page_cfg.get("category") == dim_key and bool(page_cfg.get("many", False)) == many:
            path = page_cfg.get("path", "")
            if path:
                # Render Jinja2 path template with a literal {slug} placeholder.
                return render_config_str(path, category={"slug": "{slug}"})
            break
    return ""


def _build_filter_config(page_cfg: dict, config: dict) -> dict:
    """Build the JS filter-config object for injection into the page."""
    site_cfg = config.get("site", {})
    filters_cfg = page_cfg.get("filters", {})
    page_path = page_cfg.get("path", "/index.html")
    stem = PurePosixPath(page_path.lstrip("/")).stem
    json_url = f"/jsons/{stem}-filter.json"

    dimensions: dict = {}
    for dim_key, dim_cfg in _iter_dimensions(filters_cfg):
        dim_type = dim_cfg.get("type", "multiselect")
        entry: dict = {
            "label": dim_cfg["label"],
            "type": dim_type,
        }
        if dim_type == "range":
            entry["unit"], entry["step"] = _range_params(dim_cfg)
        elif dim_type == "text":
            # Text dim: JS full-text substring match over listed record fields.
            entry["searchFields"] = list(dim_cfg.get("search_fields", []))
        else:
            entry["sort"] = dim_cfg.get("sort", "count")
            if dim_cfg.get("many"):
                entry["many"] = True
        dimensions[dim_key] = entry

    sort_records = None
    if filters_cfg.get("sort_records") is not None:
        params = _sort_records_params(filters_cfg["sort_records"])
        sort_records = {"param": params["param"], "options": params["options"]}

    photos_base_url = config.get("sources", {}).get("photos", {}).get("base_url", "").rstrip("/")

    return {
        "jsonUrl": json_url,
        "basePath": page_cfg.get("path", "/index.html"),
        "photosBaseUrl": photos_base_url,
        "pageSize": page_cfg.get("paginate_by") or site_cfg.get("paginate_by") or 0,
        "gridSelector": "[data-filter-grid]",
        "paginationWindow": site_cfg.get("pagination_window", 2),
        "paginationBoundary": site_cfg.get("pagination_boundary", 1),
        "facets": bool(filters_cfg.get("facets", False)),
        "facetsMode": filters_cfg.get("facets_mode", "hide"),
        "dimensions": dimensions,
        "sortRecords": sort_records,
    }


class FiltersPlugin:
    @hookimpl
    def prepare_jinja2_environment(self, env, config, config_dir):
        """Insert plugin templates into the Jinja2 loader chain."""
        register_plugin_templates(env, _PLUGIN_TEMPLATES)

    @hookimpl
    def copy_plugin_assets(self, output_dir, config, config_dir):
        """Copy plugin JS/CSS assets to ``<output>/krizky-filters/`` on every build."""
        replace_tree(_PLUGIN_ASSETS / "krizky-filters", output_dir / "krizky-filters")

    @hookimpl
    def extra_template_vars(self, config, config_dir, conn):
        """Compute page_filters: distinct dimension values per filter page."""
        main_table = _get_main_table(config)
        page_filters: dict = {}

        for page_name, page_cfg in config.get("site", {}).get("pages", {}).items():
            if "filters" not in page_cfg:
                continue
            filters_cfg = page_cfg["filters"]
            _warn_invalid_filters(page_name, filters_cfg)
            dims: dict = {}
            for dim_key, dim_cfg in _iter_dimensions(filters_cfg):
                if dim_cfg.get("type") == "text":
                    # Text dim has no discrete values — widget is a text input.
                    dims[dim_key] = {
                        "label": dim_cfg["label"],
                        "type": "text",
                        "values": [],
                        "js_only": True,
                    }
                    continue
                if dim_cfg.get("type") == "range":
                    # Range dim: JS computes min/max from the JSON; no values here.
                    unit, step = _range_params(dim_cfg)
                    dims[dim_key] = {
                        "label": dim_cfg["label"],
                        "type": "range",
                        "values": [],
                        "js_only": True,
                        "unit": unit,
                        "step": step,
                    }
                    continue
                url_template = _resolve_url_template(config, dim_key, dim_cfg)
                dims[dim_key] = {
                    "label": dim_cfg["label"],
                    "type": dim_cfg.get("type", "multiselect"),
                    "many": dim_cfg.get("many", False),
                    "values": fetch_filter_values(conn, main_table, dim_key, dim_cfg, url_template),
                    "js_only": not url_template,
                }
            if filters_cfg.get("sort_records") is not None:
                dims["_sort_records"] = _sort_records_params(filters_cfg["sort_records"])
            # _card_template is consumed by _filter_card_template.html
            dims["_card_template"] = filters_cfg.get("card_template")
            page_filters[page_name] = dims

        return {"page_filters": page_filters}

    @hookimpl
    def inject_head(self, page_cfg, config):
        """Return CSS link and inline ``filter-js`` class script for pages with filters:."""
        if "filters" not in page_cfg:
            return None
        return (
            '<link rel="stylesheet" href="/krizky-filters/filters.css">\n'
            "<script>document.documentElement.classList.add('filter-js')</script>"
        )

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
        """Generate filter JSON for pages with filters:."""
        if "filters" not in page_cfg:
            return
        generate_filter_json(page_cfg, records, output_dir, html_path)


plugin = FiltersPlugin()
