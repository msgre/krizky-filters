"""Fetch distinct filter dimension values from the database."""

import sqlite3

from krizky.db import fetch_distinct_categories, fetch_distinct_tags


def fetch_filter_values(
    conn: sqlite3.Connection,
    main_table: str,
    dim_key: str,
    dim_cfg: dict,
) -> list[dict]:
    """Return distinct values for one filter dimension.

    Returns a list of dicts with keys: value, slug, fallback_url.
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

    return [
        {
            "value": v,
            "slug": s,
            "fallback_url": fallback_tpl.replace("{slug}", s) if fallback_tpl else "",
        }
        for v, s in pairs
    ]
