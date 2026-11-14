# Specifikace: filters-core-helpers

- **Repo:** `krizky-filters`
- **Zdroj:** konsolidace do core, rozhodnuto 2026-11-13. Core v běhu `plugin-helpers` (`/Users/msgre/projects/muzeum/krizky/.swarm/plugin-helpers/spec.md`) přidal hook `copy_plugin_assets` a modul `krizky.plugin_helpers` s funkcemi `register_plugin_templates` a `replace_tree`. Core má verzi 0.2.0.
- **Předpoklad:** běh `plugin-helpers` je sloučený v `main` repa `msgre/krizky`.

## Cíl

Plugin přestane opakovat kód, který převzal core: registraci šablon a kopírování assetů s vlastním hlídáním opakování. Chování pro uživatele zůstane stejné, až na změnu v části 3.

## 1. Závislost na core 0.2

- `pyproject.toml`: `krizky>=0.2`.
- `uv lock --upgrade-package krizky`, aby `uv.lock` obsahoval core s `plugin_helpers`.

**Akceptace:** `uv.lock` obsahuje `krizky` ve verzi 0.2.0 nebo vyšší.

## 2. Registrace šablon

- `prepare_jinja2_environment` volá `register_plugin_templates(env, _PLUGIN_TEMPLATES)` místo vlastní manipulace s `ChoiceLoader`.
- Import `ChoiceLoader` a `FileSystemLoader` zmizí, pokud ho už nic nepotřebuje.

**Akceptace:** stávající testy, které vykreslují šablony pluginu (běh `js-only-widget`), projdou, v `plugin.py` není `ChoiceLoader`.

## 3. Kopírování assetů přes hook `copy_plugin_assets`

- Nový `@hookimpl copy_plugin_assets(self, output_dir, config, config_dir)`: `replace_tree(_PLUGIN_ASSETS / "krizky-filters", output_dir / "krizky-filters")`. Sémantika (smazat a zkopírovat znovu) je stejná jako dnes.
- `after_page_written` už nic nekopíruje, jen generuje JSON filtru.
- Odstranit `_copy_assets`, `_assets_copied`, `__init__` (pokud zůstane prázdný) a import `shutil`, pokud ho už nic nepotřebuje.

**Změna chování (záměrná):** assety se zkopírují v každém buildu, i když žádná stránka nemá `filters:`. Do HTML se dál vkládají jen na stránkách s `filters:`.

**Akceptace (testy):**
- `copy_plugin_assets` zkopíruje `filters.js` a `filters.css` do `output_dir/krizky-filters/`.
- Soubor, který v `output_dir/krizky-filters/` zůstal z dřívějška, po volání zmizí.
- `after_page_written` nevytvoří `output_dir/krizky-filters/`.

## 4. Dokumentace (docs-sync)

- `README.md`: v tabulce hooků (řádek `after_page_written`) už není kopírování assetů, přibude řádek `copy_plugin_assets`.
- `docs/configuration.md`: věta o kopírování `filters.css` (dnes „kopírováno idempotentně při každém buildu“) odpovídá novému chování.

**Akceptace:** `scripts/verify` projde.

## Mimo rozsah

- Čtení `sources.photos.base_url` z configu photos.
