---
id: "01"
slug: core-helpers
title: Přechod na krizky 0.2 (register_plugin_templates, copy_plugin_assets)
status: done
depends_on: []
files:
  - pyproject.toml
  - uv.lock
  - krizky_filters/plugin.py
  - tests/test_filter_plugin.py
  - README.md
  - docs/configuration.md
attempts: 1
pr: "8"
---

## Cíl
Plugin přestane opakovat kód, který převzal core 0.2: registraci šablon (`krizky.plugin_helpers.register_plugin_templates`) a kopírování assetů (hook `copy_plugin_assets` + `krizky.plugin_helpers.replace_tree`). Pokrývá celou specifikaci `.swarm/filters-core-helpers/spec.md`, části 1–4. Části spolu souvisí (bez core 0.2 nejde import, dokumentace popisuje nové chování), proto jsou v jednom tiketu.

## Akceptační kritéria
- `pyproject.toml` má závislost `krizky>=0.2`; `uv.lock` obsahuje `krizky` ve verzi 0.2.0 nebo vyšší (`uv lock --upgrade-package krizky`).
- `FiltersPlugin.prepare_jinja2_environment` volá jen `register_plugin_templates(env, _PLUGIN_TEMPLATES)`; `git grep -n ChoiceLoader -- krizky_filters ':!.swarm'` nic nenajde, import `ChoiceLoader`/`FileSystemLoader` z `plugin.py` zmizel.
- Nový `@hookimpl copy_plugin_assets(self, output_dir, config, config_dir)` volá `replace_tree(_PLUGIN_ASSETS / "krizky-filters", output_dir / "krizky-filters")`.
- `after_page_written` jen generuje filter JSON (pro stránky s `filters:`), nic nekopíruje; docstring tomu odpovídá.
- Z `plugin.py` zmizely `_copy_assets`, `_assets_copied`, prázdný `__init__` a import `shutil` (`git grep -n -e _copy_assets -e _assets_copied -e "import shutil" -- krizky_filters ':!.swarm'` nic nenajde).
- `README.md`: řádek `after_page_written` v tabulce hooků už nezmiňuje kopírování assetů, přibyl řádek `copy_plugin_assets`.
- `docs/configuration.md`: věta o `filters.css` (dnes „kopírováno idempotentně při každém buildu“) popisuje nové chování: assety se kopírují (přepíší) v každém buildu bez ohledu na to, zda nějaká stránka má `filters:`; do HTML se vkládají jen na stránkách s `filters:`.
- Stávající testy vykreslování šablon (`test_render_*`, `test_js_only_flags`) dál procházejí.
- `scripts/verify` skončí s exit 0.

## Testy
Nejdřív (TDD) v `tests/test_filter_plugin.py`:
- `test_copy_plugin_assets_copies_files`: `FiltersPlugin().copy_plugin_assets(output_dir=tmp_path, config=minimal_config, config_dir=tmp_path)` vytvoří `tmp_path/krizky-filters/filters.js` a `filters.css`.
- `test_copy_plugin_assets_removes_stale`: soubor předem vytvořený v `tmp_path/krizky-filters/` po volání zmizí.
- `test_after_page_written_does_not_copy_assets`: `after_page_written` pro stránku s `filters:` vygeneruje JSON, ale nevytvoří `tmp_path/krizky-filters/`.
- Volitelně test, že `prepare_jinja2_environment` na `ChoiceLoader` env vloží šablony pluginu (např. `env.get_template("_filter_widget.html")` jde načíst).

Stávající `test_after_page_written_copies_assets` a `test_after_page_written_idempotent` testují odstraňované chování: přepiš je na nové testy výše nebo je smaž. `test_after_page_written_generates_json` a `test_after_page_written_skips_no_filters` zachovej.

## Poznámky
- Core je v `origin/main` repa `msgre/krizky` (verze 0.2.0, merge PR #8). Lokální checkout `/Users/msgre/projects/muzeum/krizky` nemusí mít `main` aktuální; zdroj závislosti v `pyproject.toml` je git URL, takže `uv lock --upgrade-package krizky` stáhne aktuální `main` z GitHubu. Do core repa nic necommituj.
- Import: `from krizky.plugin_helpers import register_plugin_templates, replace_tree`.
- `replace_tree` sám vytvoří chybějící rodičovské adresáře a smaže starý cíl.
- Specifikace výslovně vylučuje změnu čtení `sources.photos.base_url`.
- Guidelines: `/Users/msgre/projects/muzeum/krizky/docs/guidelines/python.md` (bez `from __future__ import annotations`), `docs-sync.md`.

## Otázky
