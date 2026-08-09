"""Fetch distinct filter dimension values from the database."""

import sqlite3

from krizky.db import fetch_distinct_categories, fetch_distinct_tags


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
) -> list[dict]:
    """Return distinct values for one filter dimension.

    Returns a list of dicts with keys: value, slug, fallback_url, count.
    For many=True dimensions the slug column is expected to be a JSON object
    mapping value → slug (krizky convention: {dim_key}_slug).
    """
    slug_col = f"{dim_key}_slug"
    many = dim_cfg.get("many", False)
    fallback_tpl = dim_cfg.get("fallback_url", "")

    pairs: list[tuple[str, str]] = (
        fetch_distinct_tags(conn, main_table, dim_key, slug_col)
        if many
        else fetch_distinct_categories(conn, main_table, dim_key, slug_col)
    )
    counts = _fetch_value_counts(conn, main_table, dim_key, many)

    return [
        {
            "value": v,
            "slug": s,
            "fallback_url": fallback_tpl.replace("{slug}", s) if fallback_tpl else "",
            "count": counts.get(v, 0),
        }
        for v, s in pairs
    ]
