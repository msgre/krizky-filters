"""Tests for krizky-filters plugin."""

import copy
import json
import logging
import re
import sqlite3
from pathlib import Path

import pytest
from jinja2 import ChoiceLoader, Environment, FileSystemLoader

from krizky_filters.json_gen import generate_filter_json
from krizky_filters.plugin import FiltersPlugin, _build_filter_config, _resolve_url_template
from krizky_filters.values import fetch_filter_values

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE mista (slug TEXT, nazev TEXT, typ TEXT, typ_slug TEXT, datace TEXT, datace_slug TEXT)"
    )
    c.executemany(
        "INSERT INTO mista VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("kriz-a", "Kříž A", "kriz", "kriz", "19. stol.", "19-stol"),
            ("kriz-b", "Kříž B", "kriz", "kriz", "18. stol.", "18-stol"),
            ("socha-a", "Socha A", "socha", "socha", "19. stol.", "19-stol"),
        ],
    )
    c.commit()
    yield c
    c.close()


@pytest.fixture
def conn_tags():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE mista (slug TEXT, nazev TEXT, stitky TEXT, stitky_slug TEXT)")
    c.executemany(
        "INSERT INTO mista VALUES (?, ?, ?, ?)",
        [
            ("a", "A", '["baroko","hrbitov"]', '{"baroko":"baroko","hrbitov":"hrbitov"}'),
            ("b", "B", '["baroko"]', '{"baroko":"baroko"}'),
            ("c", "C", '["pramen"]', '{"pramen":"pramen"}'),
        ],
    )
    c.commit()
    yield c
    c.close()


@pytest.fixture
def minimal_config():
    return {
        "sources": {"tables": {"mista": {"main": True}}},
        "site": {
            "order_by": "rowid",
            "ordering": "asc",
            "paginate_by": 10,
            "pages": {
                "vsechna_mista": {
                    "path": "/vsechna-mista.html",
                    "template": "vsechna_mista.html",
                    "filters": {
                        "fields": ["slug", "nazev", "typ"],
                        "card_template": "_karta.html",
                        "dimensions": {
                            "typ": {"label": "Typ", "type": "select"},
                            "datace": {"label": "Datace", "type": "select"},
                        },
                    },
                }
            },
        },
    }


# ── values.py ─────────────────────────────────────────────────────────────────


def test_fetch_filter_values_plain(conn):
    dim_cfg = {"label": "Typ", "type": "select"}
    values = fetch_filter_values(conn, "mista", "typ", dim_cfg, url_template="/typy/{slug}.html")
    slugs = [v["slug"] for v in values]
    assert "kriz" in slugs
    assert "socha" in slugs
    assert all(v["url"].startswith("/typy/") for v in values)


def test_fetch_filter_values_no_url(conn):
    values = fetch_filter_values(conn, "mista", "typ", {"label": "Typ", "type": "select"})
    assert all(v["url"] == "" for v in values)


def test_fetch_filter_values_many(conn_tags):
    dim_cfg = {"label": "Štítek", "type": "multiselect", "many": True}
    values = fetch_filter_values(conn_tags, "mista", "stitky", dim_cfg)
    slugs = [v["slug"] for v in values]
    assert "baroko" in slugs
    assert "hrbitov" in slugs
    assert "pramen" in slugs


def test_fetch_filter_values_structure(conn):
    values = fetch_filter_values(conn, "mista", "typ", {"label": "Typ", "type": "select"})
    for v in values:
        assert "value" in v
        assert "slug" in v
        assert "url" in v
        assert "count" in v


def test_fetch_filter_values_sort_by_count(conn):
    """Default sort: most frequent first."""
    values = fetch_filter_values(conn, "mista", "typ", {"label": "Typ", "type": "select"})
    # Fixture has 2× kriz, 1× socha → kriz first
    assert values[0]["slug"] == "kriz"
    assert values[0]["count"] == 2
    assert values[1]["slug"] == "socha"
    assert values[1]["count"] == 1


def test_fetch_filter_values_sort_alpha(conn):
    """Explicit sort: alpha (locale-friendly, diacritics stripped)."""
    values = fetch_filter_values(
        conn,
        "mista",
        "typ",
        {"label": "Typ", "type": "select", "sort": "alpha"},
    )
    # kriz < socha alphabetically
    assert [v["slug"] for v in values] == ["kriz", "socha"]


def test_fetch_filter_values_sort_alpha_diacritics():
    """'č' should sort near 'c', not after 'z'."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE t (val TEXT, val_slug TEXT)")
    c.executemany(
        "INSERT INTO t VALUES (?, ?)",
        [
            ("zebra", "zebra"),
            ("čáp", "cap"),
            ("banán", "banan"),
        ],
    )
    c.commit()
    values = fetch_filter_values(
        c,
        "t",
        "val",
        {"label": "V", "type": "select", "sort": "alpha"},
    )
    slugs = [v["slug"] for v in values]
    # Expected: banán, čáp, zebra (č sorts with c, not after z)
    assert slugs == ["banan", "cap", "zebra"]
    c.close()


def test_fetch_filter_values_sort_explicit_multicolumn(conn):
    """Explicit multi-column: -count,alpha equivalent to preset 'count'."""
    v1 = fetch_filter_values(
        conn, "mista", "typ", {"label": "T", "type": "select", "sort": "count"}
    )
    v2 = fetch_filter_values(
        conn, "mista", "typ", {"label": "T", "type": "select", "sort": "-count,alpha"}
    )
    assert [v["slug"] for v in v1] == [v["slug"] for v in v2]


def test_fetch_filter_values_sort_reversed_priority(conn):
    """Alpha ASC as primary, count DESC as tiebreaker."""
    values = fetch_filter_values(
        conn, "mista", "typ", {"label": "T", "type": "select", "sort": "alpha,-count"}
    )
    # kriz < socha alphabetically, so kriz first regardless of count
    assert [v["slug"] for v in values] == ["kriz", "socha"]


def test_fetch_filter_values_sort_alpha_desc():
    """Alpha DESC sorts Z→A."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE t (val TEXT, val_slug TEXT)")
    c.executemany(
        "INSERT INTO t VALUES (?, ?)",
        [
            ("apple", "apple"),
            ("banana", "banana"),
            ("cherry", "cherry"),
        ],
    )
    c.commit()
    values = fetch_filter_values(
        c,
        "t",
        "val",
        {"label": "V", "type": "select", "sort": "-alpha"},
    )
    assert [v["slug"] for v in values] == ["cherry", "banana", "apple"]
    c.close()


def test_fetch_filter_values_sort_invalid_field(conn):
    """Unknown field should raise a clear ValueError."""
    with pytest.raises(ValueError, match="Unknown sort field"):
        fetch_filter_values(
            conn, "mista", "typ", {"label": "T", "type": "select", "sort": "banana"}
        )


def test_fetch_filter_values_sort_explicit_order():
    """sort: {order: [...]} places listed values first in that order."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE t (val TEXT, val_slug TEXT)")
    c.executemany(
        "INSERT INTO t VALUES (?, ?)",
        [
            ("2. polovina 19. století", "2-19"),
            ("1. polovina 20. století", "1-20"),
            ("1. polovina 19. století", "1-19"),
            ("2. polovina 20. století", "2-20"),
        ],
    )
    c.commit()
    values = fetch_filter_values(
        c,
        "t",
        "val",
        {
            "label": "V",
            "type": "select",
            "sort": {
                "order": [
                    "1. polovina 19. století",
                    "2. polovina 19. století",
                    "1. polovina 20. století",
                    "2. polovina 20. století",
                ]
            },
        },
    )
    assert [v["value"] for v in values] == [
        "1. polovina 19. století",
        "2. polovina 19. století",
        "1. polovina 20. století",
        "2. polovina 20. století",
    ]
    c.close()


def test_fetch_filter_values_sort_order_with_extras():
    """Values not in order list go to end, sorted by fallback."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE t (val TEXT, val_slug TEXT)")
    c.executemany(
        "INSERT INTO t VALUES (?, ?)",
        [
            ("baroko", "baroko"),
            ("gotika", "gotika"),
            ("renesance", "renesance"),  # not in order
            ("empír", "empir"),  # not in order
        ],
    )
    c.commit()
    values = fetch_filter_values(
        c,
        "t",
        "val",
        {
            "label": "V",
            "type": "select",
            "sort": {
                "order": ["gotika", "baroko"],
                "fallback": "alpha",  # rest alphabetically
            },
        },
    )
    slugs = [v["slug"] for v in values]
    # gotika, baroko (in order) → empir, renesance (alpha for rest)
    assert slugs == ["gotika", "baroko", "empir", "renesance"]
    c.close()


def test_fetch_filter_values_sort_order_empty_list(conn):
    """Empty order list falls back to fallback spec."""
    values = fetch_filter_values(
        conn,
        "mista",
        "typ",
        {"label": "T", "type": "select", "sort": {"order": [], "fallback": "alpha"}},
    )
    assert [v["slug"] for v in values] == ["kriz", "socha"]


# ── json_gen.py ───────────────────────────────────────────────────────────────


def test_generate_filter_json_fields_subset(tmp_path):
    records = [{"slug": "a", "nazev": "A", "extra": "drop"}]
    page_cfg = {"filters": {"fields": ["slug", "nazev"]}}
    generate_filter_json(page_cfg, records, tmp_path, "/vsechna-mista.html")
    data = json.loads((tmp_path / "jsons" / "vsechna-mista-filter.json").read_text())
    assert data == [{"slug": "a", "nazev": "A"}]


def test_generate_filter_json_all_fields(tmp_path):
    records = [{"slug": "a", "nazev": "A", "extra": "keep"}]
    page_cfg = {"filters": {"dimensions": {"typ": {"label": "Typ", "type": "select"}}}}
    generate_filter_json(page_cfg, records, tmp_path, "/mista.html")
    data = json.loads((tmp_path / "jsons" / "mista-filter.json").read_text())
    assert data[0]["extra"] == "keep"


def test_generate_filter_json_path_derivation(tmp_path):
    page_cfg = {"filters": {}}
    generate_filter_json(page_cfg, [], tmp_path, "/vsechna-mista.html")
    assert (tmp_path / "jsons" / "vsechna-mista-filter.json").exists()


def test_generate_filter_json_creates_jsons_dir(tmp_path):
    page_cfg = {"filters": {}}
    generate_filter_json(page_cfg, [], tmp_path, "/page.html")
    assert (tmp_path / "jsons").is_dir()


# ── plugin.py — _build_filter_config ─────────────────────────────────────────


def test_build_filter_config_json_url(minimal_config):
    page_cfg = minimal_config["site"]["pages"]["vsechna_mista"]
    cfg = _build_filter_config(page_cfg, minimal_config)
    assert cfg["jsonUrl"] == "/jsons/vsechna-mista-filter.json"


def test_build_filter_config_dimensions(minimal_config):
    page_cfg = minimal_config["site"]["pages"]["vsechna_mista"]
    cfg = _build_filter_config(page_cfg, minimal_config)
    assert "typ" in cfg["dimensions"]
    assert "datace" in cfg["dimensions"]
    assert "fields" not in cfg["dimensions"]
    assert "card_template" not in cfg["dimensions"]
    assert cfg["dimensions"]["typ"]["type"] == "select"


def test_build_filter_config_no_url_in_dimensions(minimal_config):
    """URL template belongs to server-side widget rendering, not to JS filter config."""
    page_cfg = dict(minimal_config["site"]["pages"]["vsechna_mista"])
    page_cfg["filters"] = {
        "dimensions": {
            "typ": {"label": "Typ", "type": "select", "url": "/typy/{slug}.html"},
        },
    }
    cfg = _build_filter_config(page_cfg, minimal_config)
    assert "url" not in cfg["dimensions"]["typ"]


def test_build_filter_config_many_flag(minimal_config):
    page_cfg = dict(minimal_config["site"]["pages"]["vsechna_mista"])
    page_cfg["filters"] = {
        "dimensions": {
            "stitky": {"label": "Štítek", "type": "multiselect", "many": True},
        },
    }
    cfg = _build_filter_config(page_cfg, minimal_config)
    assert cfg["dimensions"]["stitky"]["many"] is True


def test_build_filter_config_page_size(minimal_config):
    page_cfg = minimal_config["site"]["pages"]["vsechna_mista"]
    cfg = _build_filter_config(page_cfg, minimal_config)
    assert cfg["pageSize"] == 10


def test_build_filter_config_facets_disabled_by_default(minimal_config):
    page_cfg = minimal_config["site"]["pages"]["vsechna_mista"]
    cfg = _build_filter_config(page_cfg, minimal_config)
    assert cfg["facets"] is False
    assert cfg["facetsMode"] == "hide"


def test_build_filter_config_facets_enabled(minimal_config):
    page_cfg = dict(minimal_config["site"]["pages"]["vsechna_mista"])
    page_cfg["filters"] = {
        "facets": True,
        "facets_mode": "disable",
        "dimensions": {"typ": {"label": "Typ", "type": "select"}},
    }
    cfg = _build_filter_config(page_cfg, minimal_config)
    assert cfg["facets"] is True
    assert cfg["facetsMode"] == "disable"


def test_build_filter_config_sort_propagated(minimal_config):
    """Sort spec must be exposed to JS so runtime re-sort matches build-time."""
    page_cfg = dict(minimal_config["site"]["pages"]["vsechna_mista"])
    page_cfg["filters"] = {
        "dimensions": {
            "typ": {"label": "Typ", "type": "select", "sort": "-count,alpha"},
            "datace": {"label": "Datace", "type": "select"},  # default
        },
    }
    cfg = _build_filter_config(page_cfg, minimal_config)
    assert cfg["dimensions"]["typ"]["sort"] == "-count,alpha"
    assert cfg["dimensions"]["datace"]["sort"] == "count"


def test_build_filter_config_text_dim(minimal_config):
    """Text dim exposes searchFields, no sort/many."""
    page_cfg = dict(minimal_config["site"]["pages"]["vsechna_mista"])
    page_cfg["filters"] = {
        "dimensions": {
            "q": {
                "label": "Hledat",
                "type": "text",
                "search_fields": ["nazev", "pribeh"],
            },
        },
    }
    cfg = _build_filter_config(page_cfg, minimal_config)
    q = cfg["dimensions"]["q"]
    assert q["type"] == "text"
    assert q["searchFields"] == ["nazev", "pribeh"]
    assert "sort" not in q
    assert "many" not in q


def test_extra_template_vars_text_dim(conn):
    """Text dims get empty values list and no DB query."""
    config = {
        "sources": {"tables": {"mista": {"main": True}}},
        "site": {
            "pages": {
                "search_page": {
                    "path": "/mista.html",
                    "filters": {
                        "dimensions": {
                            "q": {
                                "label": "Hledat",
                                "type": "text",
                                "search_fields": ["nazev"],
                            },
                        },
                    },
                },
            },
        },
    }
    p = FiltersPlugin()
    result = p.extra_template_vars(config=config, config_dir=Path("."), conn=conn)
    q_dim = result["page_filters"]["search_page"]["q"]
    assert q_dim["type"] == "text"
    assert q_dim["label"] == "Hledat"
    assert q_dim["values"] == []


# ── plugin.py — config warnings ──────────────────────────────────────────────


def _run_extra_vars(conn, config, caplog):
    caplog.set_level(logging.WARNING, logger="krizky_filters.plugin")
    FiltersPlugin().extra_template_vars(config=config, config_dir=Path("."), conn=conn)
    return [r for r in caplog.records if r.name == "krizky_filters.plugin"]


def _config_with(minimal_config, **filters_override):
    config = copy.deepcopy(minimal_config)
    config["site"]["pages"]["vsechna_mista"]["filters"].update(filters_override)
    return config


def test_no_warnings_for_valid_config(conn, minimal_config, caplog):
    assert _run_extra_vars(conn, minimal_config, caplog) == []


def test_no_warnings_for_valid_text_dim(conn, caplog):
    config = {
        "sources": {"tables": {"mista": {"main": True}}},
        "site": {
            "pages": {
                "search_page": {
                    "filters": {
                        "dimensions": {
                            "q": {"label": "H", "type": "text", "search_fields": ["nazev"]},
                        },
                    },
                },
            },
        },
    }
    assert _run_extra_vars(conn, config, caplog) == []


def test_warning_unknown_dimension_type(conn, minimal_config, caplog):
    dims = {"typ": {"label": "Typ", "type": "radio"}}
    config = _config_with(minimal_config, dimensions=dims)
    records = _run_extra_vars(conn, config, caplog)
    assert len(records) == 1
    msg = records[0].getMessage()
    assert "vsechna_mista" in msg
    assert "typ" in msg
    assert "radio" in msg


@pytest.mark.parametrize("search_fields", [None, []])
def test_warning_text_dim_without_search_fields(conn, minimal_config, caplog, search_fields):
    dim = {"label": "Hledat", "type": "text"}
    if search_fields is not None:
        dim["search_fields"] = search_fields
    config = _config_with(minimal_config, dimensions={"q": dim})
    records = _run_extra_vars(conn, config, caplog)
    assert len(records) == 1
    msg = records[0].getMessage()
    assert "vsechna_mista" in msg
    assert "'q'" in msg


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        ("bogus", ValueError),
        ("-count,nope", ValueError),
        ({"order": ["kriz"], "fallback": "bogus"}, ValueError),
        ({"fallback": "count"}, AttributeError),
    ],
)
def test_warning_invalid_sort(conn, minimal_config, caplog, sort, expected):
    dims = {"typ": {"label": "Typ", "type": "select", "sort": sort}}
    config = _config_with(minimal_config, dimensions=dims)
    caplog.set_level(logging.WARNING, logger="krizky_filters.plugin")
    # Invalid sort fails the build today; the warning must not change that.
    with pytest.raises(expected):
        FiltersPlugin().extra_template_vars(config=config, config_dir=Path("."), conn=conn)
    records = [r for r in caplog.records if r.name == "krizky_filters.plugin"]
    assert len(records) == 1
    msg = records[0].getMessage()
    assert "vsechna_mista" in msg
    assert "typ" in msg


@pytest.mark.parametrize(
    "sort",
    [
        None,
        "alpha",
        "-count,alpha",
        {"order": ["kriz"], "fallback": "-alpha"},
        {"order": ["kriz"]},
        {"order": ["kriz"], "fallback": None},
    ],
)
def test_no_warning_for_valid_sort(conn, minimal_config, caplog, sort):
    dims = {"typ": {"label": "Typ", "type": "select", "sort": sort}}
    config = _config_with(minimal_config, dimensions=dims)
    assert _run_extra_vars(conn, config, caplog) == []


def test_warning_invalid_sort_ignored_for_text_dim(conn, minimal_config, caplog):
    dims = {"q": {"label": "H", "type": "text", "search_fields": ["nazev"], "sort": "bogus"}}
    config = _config_with(minimal_config, dimensions=dims)
    assert _run_extra_vars(conn, config, caplog) == []


def test_warning_unknown_facets_mode(conn, minimal_config, caplog):
    config = _config_with(minimal_config, facets_mode="dim")
    records = _run_extra_vars(conn, config, caplog)
    assert len(records) == 1
    msg = records[0].getMessage()
    assert "vsechna_mista" in msg
    assert "dim" in msg


@pytest.mark.parametrize("mode", ["hide", "disable"])
def test_no_warning_for_valid_facets_mode(conn, minimal_config, caplog, mode):
    config = _config_with(minimal_config, facets_mode=mode)
    assert _run_extra_vars(conn, config, caplog) == []


@pytest.mark.parametrize("filters_cfg", [{}, {"dimensions": {}}])
def test_warning_filters_without_dimensions(conn, minimal_config, caplog, filters_cfg):
    config = copy.deepcopy(minimal_config)
    config["site"]["pages"]["vsechna_mista"]["filters"] = filters_cfg
    records = _run_extra_vars(conn, config, caplog)
    assert len(records) == 1
    assert "vsechna_mista" in records[0].getMessage()


# ── plugin.py — _resolve_url_template ────────────────────────────────────────


def test_resolve_url_template_explicit():
    """Explicit url in dim config wins."""
    config = {"site": {"pages": {}}}
    url = _resolve_url_template(config, "typ", {"url": "/custom/{slug}.html"})
    assert url == "/custom/{slug}.html"


def test_resolve_url_template_from_category_page():
    """Auto-detect URL from matching category page."""
    config = {
        "site": {
            "pages": {
                "kategorie": {
                    "category": "typ",
                    "path": "/kategorie/{{ category.slug }}.html",
                },
            },
        },
    }
    url = _resolve_url_template(config, "typ", {})
    assert url == "/kategorie/{slug}.html"


def test_resolve_url_template_matches_many_flag():
    """Auto-detect must match `many` between dim and page."""
    config = {
        "site": {
            "pages": {
                "stitky_page": {
                    "category": "stitky",
                    "many": True,
                    "path": "/stitek/{{ category.slug }}.html",
                },
            },
        },
    }
    # dim with many=True → matches
    url = _resolve_url_template(config, "stitky", {"many": True})
    assert url == "/stitek/{slug}.html"
    # dim with many=False → no match
    url = _resolve_url_template(config, "stitky", {"many": False})
    assert url == ""


def test_resolve_url_template_no_match():
    config = {"site": {"pages": {"other": {"path": "/other.html"}}}}
    assert _resolve_url_template(config, "typ", {}) == ""


# ── plugin.py — inject_head / inject_body_end ─────────────────────────────────


def test_inject_head_with_filters(minimal_config):
    p = FiltersPlugin()
    page_cfg = minimal_config["site"]["pages"]["vsechna_mista"]
    result = p.inject_head(page_cfg=page_cfg, config=minimal_config)
    assert result is not None
    assert "filters.css" in result
    assert "<link" in result
    assert "<script>" in result
    assert "classList.add('filter-js')" in result


def test_inject_head_without_filters(minimal_config):
    p = FiltersPlugin()
    result = p.inject_head(page_cfg={"path": "/index.html"}, config=minimal_config)
    assert result is None


def test_inject_body_end_with_filters(minimal_config):
    p = FiltersPlugin()
    page_cfg = minimal_config["site"]["pages"]["vsechna_mista"]
    result = p.inject_body_end(page_cfg=page_cfg, config=minimal_config)
    assert result is not None
    assert 'id="filter-config"' in result
    assert "filters.js" in result
    # Embedded JSON must be valid
    json_part = result.split(">")[1].split("</")[0]
    parsed = json.loads(json_part)
    assert "jsonUrl" in parsed
    assert "dimensions" in parsed


def test_inject_body_end_without_filters(minimal_config):
    p = FiltersPlugin()
    result = p.inject_body_end(page_cfg={"path": "/index.html"}, config=minimal_config)
    assert result is None


# ── plugin.py — extra_template_vars ──────────────────────────────────────────


def test_extra_template_vars_structure(conn, minimal_config):
    p = FiltersPlugin()
    result = p.extra_template_vars(config=minimal_config, config_dir=Path("."), conn=conn)
    assert "page_filters" in result
    pf = result["page_filters"]
    assert "vsechna_mista" in pf
    dims = pf["vsechna_mista"]
    assert "typ" in dims
    assert "datace" in dims
    assert dims["typ"]["label"] == "Typ"
    assert isinstance(dims["typ"]["values"], list)


def test_extra_template_vars_card_template(conn, minimal_config):
    p = FiltersPlugin()
    result = p.extra_template_vars(config=minimal_config, config_dir=Path("."), conn=conn)
    assert result["page_filters"]["vsechna_mista"]["_card_template"] == "_karta.html"


def test_extra_template_vars_skips_non_filter_pages(conn):
    config = {
        "sources": {"tables": {"mista": {"main": True}}},
        "site": {
            "pages": {
                "home": {"path": "/index.html", "template": "index.html"},
                "filter_page": {
                    "path": "/mista.html",
                    "template": "mista.html",
                    "filters": {
                        "dimensions": {
                            "typ": {"label": "Typ", "type": "select"},
                        },
                    },
                },
            }
        },
    }
    p = FiltersPlugin()
    result = p.extra_template_vars(config=config, config_dir=Path("."), conn=conn)
    assert "home" not in result["page_filters"]
    assert "filter_page" in result["page_filters"]


def test_extra_template_vars_no_filter_pages(conn):
    config = {
        "sources": {"tables": {"mista": {"main": True}}},
        "site": {"pages": {"home": {"path": "/index.html", "template": "index.html"}}},
    }
    p = FiltersPlugin()
    result = p.extra_template_vars(config=config, config_dir=Path("."), conn=conn)
    assert result["page_filters"] == {}


def test_extra_template_vars_auto_detects_url(conn):
    """URL is auto-detected from a matching category page when not explicit."""
    config = {
        "sources": {"tables": {"mista": {"main": True}}},
        "site": {
            "pages": {
                "kategorie": {
                    "category": "typ",
                    "path": "/kategorie/{{ category.slug }}.html",
                },
                "filter_page": {
                    "path": "/mista.html",
                    "filters": {
                        "dimensions": {"typ": {"label": "Typ", "type": "select"}},
                    },
                },
            },
        },
    }
    p = FiltersPlugin()
    result = p.extra_template_vars(config=config, config_dir=Path("."), conn=conn)
    values = result["page_filters"]["filter_page"]["typ"]["values"]
    # Every fetched value should have URL derived from the category page's path.
    for v in values:
        assert v["url"].startswith("/kategorie/")
        assert v["url"].endswith(".html")


# ── plugin.py — after_page_written ───────────────────────────────────────────


def test_copy_plugin_assets_copies_files(tmp_path, minimal_config):
    FiltersPlugin().copy_plugin_assets(
        output_dir=tmp_path, config=minimal_config, config_dir=tmp_path
    )
    assert (tmp_path / "krizky-filters" / "filters.js").exists()
    assert (tmp_path / "krizky-filters" / "filters.css").exists()


def test_copy_plugin_assets_removes_stale(tmp_path, minimal_config):
    stale = tmp_path / "krizky-filters" / "stale.txt"
    stale.parent.mkdir()
    stale.write_text("old")
    FiltersPlugin().copy_plugin_assets(
        output_dir=tmp_path, config=minimal_config, config_dir=tmp_path
    )
    assert not stale.exists()
    assert (tmp_path / "krizky-filters" / "filters.js").exists()


def test_after_page_written_does_not_copy_assets(tmp_path, minimal_config):
    page_cfg = minimal_config["site"]["pages"]["vsechna_mista"]
    FiltersPlugin().after_page_written(
        page_cfg=page_cfg,
        html_path="/vsechna-mista.html",
        output_dir=tmp_path,
        records=[],
        config=minimal_config,
    )
    assert (tmp_path / "jsons" / "vsechna-mista-filter.json").exists()
    assert not (tmp_path / "krizky-filters").exists()


def test_prepare_jinja2_environment_registers_templates(tmp_path, minimal_config):
    env = Environment(loader=ChoiceLoader([FileSystemLoader(str(tmp_path))]))
    FiltersPlugin().prepare_jinja2_environment(env, minimal_config, tmp_path)
    assert env.get_template("_filter_widget.html")


def test_after_page_written_generates_json(tmp_path, minimal_config):
    p = FiltersPlugin()
    page_cfg = minimal_config["site"]["pages"]["vsechna_mista"]
    records = [{"slug": "a", "nazev": "A", "typ": "kriz"}]
    p.after_page_written(
        page_cfg=page_cfg,
        html_path="/vsechna-mista.html",
        output_dir=tmp_path,
        records=records,
        config=minimal_config,
    )
    json_path = tmp_path / "jsons" / "vsechna-mista-filter.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert data[0]["slug"] == "a"
    assert "nazev" in data[0]


def test_after_page_written_skips_no_filters(tmp_path, minimal_config):
    p = FiltersPlugin()
    p.after_page_written(
        page_cfg={"path": "/index.html"},
        html_path="/index.html",
        output_dir=tmp_path,
        records=[],
        config=minimal_config,
    )
    assert not (tmp_path / "krizky-filters").exists()
    assert not (tmp_path / "jsons").exists()


# ── js_only + vykreslení šablon ───────────────────────────────────────────────


def _js_only_config(typ_dim: dict, with_category_page: bool = False) -> dict:
    pages: dict = {
        "mista": {
            "path": "/mista.html",
            "filters": {
                "dimensions": {
                    "q": {"label": "Hledat", "type": "text", "search_fields": ["nazev"]},
                    "typ": {"label": "Typ", **typ_dim},
                },
            },
        },
    }
    if with_category_page:
        pages["typ_page"] = {"path": "/typ/{{ category.slug }}.html", "category": "typ"}
    return {"sources": {"tables": {"mista": {"main": True}}}, "site": {"pages": pages}}


def _page_filters(conn, config: dict) -> dict:
    result = FiltersPlugin().extra_template_vars(config=config, config_dir=Path("."), conn=conn)
    return result["page_filters"]


@pytest.mark.parametrize("dim_type", ["select", "multiselect"])
def test_js_only_flags(conn, dim_type):
    pf = _page_filters(conn, _js_only_config({"type": dim_type, "url": "/typ/{slug}.html"}))
    assert pf["mista"]["q"]["js_only"] is True
    assert pf["mista"]["typ"]["js_only"] is False

    pf = _page_filters(conn, _js_only_config({"type": dim_type}, with_category_page=True))
    assert pf["mista"]["typ"]["js_only"] is False

    pf = _page_filters(conn, _js_only_config({"type": dim_type}))
    assert pf["mista"]["typ"]["js_only"] is True


def test_card_template_has_no_js_only(conn):
    pf = _page_filters(conn, _js_only_config({"type": "select"}))
    assert pf["mista"]["_card_template"] is None


_TEMPLATES = Path(__file__).parent.parent / "krizky_filters" / "templates"


def _render(conn, config: dict, template: str = "_filter_widget.html") -> str:
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES)), autoescape=True)
    pf = _page_filters(conn, config)
    return env.get_template(template).render(page_name="mista", page_filters=pf)


def _tag(html: str, marker: str) -> str:
    """Return the opening tag containing ``marker``."""
    m = re.search(r"<[^<>]*" + re.escape(marker) + r"[^<>]*>", html)
    assert m, f"{marker} not found"
    return m.group(0)


@pytest.mark.parametrize("dim_type", ["select", "multiselect"])
def test_render_option_hrefs(conn, dim_type):
    html = _render(conn, _js_only_config({"type": dim_type, "url": "/typ/{slug}.html"}))
    assert 'href="/typ/kriz.html"' in html
    assert 'href="#"' not in html
    html = _render(conn, _js_only_config({"type": dim_type}))
    assert 'href="#"' in html
    assert "/typ/kriz.html" not in html


def test_render_js_only_attributes_mixed(conn):
    html = _render(conn, _js_only_config({"type": "select", "url": "/typ/{slug}.html"}))
    assert "data-filter-js-only" in _tag(html, 'data-dimension="q"')
    assert "data-filter-js-only" not in _tag(html, 'data-dimension="typ"')
    assert "data-filter-js-only" not in _tag(html, "data-filter-widget")


def test_render_js_only_attributes_all_js_only(conn):
    html = _render(conn, _js_only_config({"type": "multiselect"}))
    assert "data-filter-js-only" in _tag(html, 'data-dimension="q"')
    assert "data-filter-js-only" in _tag(html, 'data-dimension="typ"')
    assert "data-filter-js-only" in _tag(html, "data-filter-widget")
