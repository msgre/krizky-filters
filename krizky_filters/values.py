"""Fetch distinct filter dimension values from the database."""

import sqlite3
import unicodedata

from krizky.db import fetch_distinct_categories, fetch_distinct_tags


def _sort_key_alpha(text: str) -> str:
    """Locale-friendly sort key: strip diacritics so 'č' sorts near 'c'."""
    normalized = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in normalized if not unicodedata.combining(c))


# Presets — shorthand for common multi-column sorts.
_SORT_ALIASES = {
    "count": "-count,alpha",   # nejčastější nahoře, abeceda jako tiebreaker
    "alpha": "alpha",           # čistě abecedně
}

_ALLOWED_SORT_FIELDS = {"count", "alpha"}


def _parse_sort(sort_spec: str) -> list[tuple[str, bool]]:
    """Parse a sort spec into a list of (field, desc) tuples.

    Accepts:
      - Preset alias: ``count`` (= ``-count,alpha``), ``alpha``
      - Explicit: comma-separated fields with optional ``-`` prefix for DESC.
        E.g. ``"-count,alpha"``, ``"alpha,-count"``, ``"-alpha"``.

    Allowed fields: ``count``, ``alpha``.
    """
    sort_spec = (sort_spec or "count").strip()
    if sort_spec in _SORT_ALIASES:
        sort_spec = _SORT_ALIASES[sort_spec]

    parsed: list[tuple[str, bool]] = []
    for part in sort_spec.split(","):
        part = part.strip()
        if not part:
            continue
        desc = part.startswith("-")
        field = part.lstrip("-").strip()
        if field not in _ALLOWED_SORT_FIELDS:
            raise ValueError(
                f"Unknown sort field '{field}' in sort spec '{sort_spec}'. "
                f"Allowed: {', '.join(sorted(_ALLOWED_SORT_FIELDS))}"
            )
        parsed.append((field, desc))
    return parsed


def _field_key(v: dict, field: str):
    if field == "count":
        return v["count"]
    if field == "alpha":
        return _sort_key_alpha(v["value"])
    return v["value"]


def _sort_by_columns(values: list[dict], sort_spec: str) -> None:
    """Sort in-place by string spec (preset alias or explicit multi-column)."""
    parsed = _parse_sort(sort_spec)
    for field, desc in reversed(parsed):
        values.sort(key=lambda v, f=field: _field_key(v, f), reverse=desc)


def _sort_values(values: list[dict], sort_spec) -> None:
    """Sort ``values`` in-place per ``sort_spec``.

    Accepts:
      - String: preset alias (``count`` | ``alpha``) or explicit multi-column
        (``-count,alpha``). Uses stable sort with least-significant key first.
      - Dict with ``order`` key: values matching the list appear in that order;
        remaining values fall back to sort by ``fallback`` spec (default: ``count``).
    """
    if isinstance(sort_spec, dict) and "order" in sort_spec:
        order_list = sort_spec["order"] or []
        fallback_spec = sort_spec.get("fallback", "count")
        order_map = {v: i for i, v in enumerate(order_list)}

        in_order = [v for v in values if v["value"] in order_map]
        rest = [v for v in values if v["value"] not in order_map]

        in_order.sort(key=lambda v: order_map[v["value"]])
        _sort_by_columns(rest, fallback_spec)

        values[:] = in_order + rest
        return

    _sort_by_columns(values, sort_spec or "count")


def _fetch_value_counts(
    conn: sqlite3.Connection,
    main_table: str,
    dim_key: str,
    many: bool,
) -> dict[str, int]:
    """Return {value: record_count} for a filter dimension."""
    if many:
        sql = (
            f"SELECT TRIM(je.value), COUNT(*)"
            f" FROM [{main_table}], json_each([{main_table}].[{dim_key}]) je"
            f" WHERE TRIM(je.value) != ''"
            f" GROUP BY TRIM(je.value)"
        )
    else:
        sql = (
            f"SELECT TRIM([{dim_key}]), COUNT(*)"
            f" FROM [{main_table}]"
            f" WHERE [{dim_key}] IS NOT NULL AND TRIM([{dim_key}]) != ''"
            f" GROUP BY TRIM([{dim_key}])"
        )
    return {row[0]: row[1] for row in conn.execute(sql).fetchall()}


def fetch_filter_values(
    conn: sqlite3.Connection,
    main_table: str,
    dim_key: str,
    dim_cfg: dict,
    url_template: str = "",
) -> list[dict]:
    """Return distinct values for one filter dimension.

    Returns a list of dicts with keys: value, slug, url, count.
    For many=True dimensions the slug column is expected to be a JSON object
    mapping value → slug (krizky convention: {dim_key}_slug).

    url_template is a string with {slug} placeholder, e.g. "/typ/{slug}.html".
    Resolution of the template is the caller's responsibility.
    """
    slug_col = f"{dim_key}_slug"
    many = dim_cfg.get("many", False)

    pairs: list[tuple[str, str]] = (
        fetch_distinct_tags(conn, main_table, dim_key, slug_col)
        if many
        else fetch_distinct_categories(conn, main_table, dim_key, slug_col)
    )
    counts = _fetch_value_counts(conn, main_table, dim_key, many)

    values = [
        {
            "value": v,
            "slug": s,
            "url": url_template.replace("{slug}", s) if url_template else "",
            "count": counts.get(v, 0),
        }
        for v, s in pairs
    ]

    _sort_values(values, dim_cfg.get("sort", "count"))
    return values
