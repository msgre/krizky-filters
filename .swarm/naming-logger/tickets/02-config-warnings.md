---
id: "02"
slug: config-warnings
title: Logger a varování při chybné konfiguraci filtrů
status: done
depends_on: ["01"]
files:
  - krizky_filters/plugin.py
  - tests/test_filter_plugin.py
  - docs/configuration.md
attempts: 2
pr: "3"
---

## Cíl
Chybná konfigurace filtrů se dnes projeví potichu: filtr nefunguje a v logu nic není. Do `krizky_filters/plugin.py` přidej modulový logger `_log` a validaci konfigurace filtrů, která v pěti popsaných případech vypíše `_log.warning`. Každé varování se vypíše jednou za build. Viz specifikace `.swarm/naming-logger/spec.md`, část 2.

## Akceptační kritéria
- `krizky_filters/plugin.py` má `import logging` a modulový `_log = logging.getLogger(__name__)`. Jméno je `_log` a formátování jde přes `%s`, ne přes f-string (`docs/guidelines/python.md`, sekce Logging).
- `_log.warning` se vypíše, když:
  1. dimenze má `type` mimo `select`, `multiselect` a `text` (chybějící `type` znamená `multiselect` a je platný),
  2. dimenze má `type: text` a chybí jí `search_fields`, nebo je seznam prázdný,
  3. `sort` dimenze obsahuje neznámý preset nebo sloupec. Platí string (preset `count`/`alpha` nebo multi-column z polí `count`/`alpha` s volitelným `-`) i dict s `order` a volitelným `fallback` (`fallback` má stejná pravidla jako string). Viz `docs/configuration.md`, Sortování,
  4. `facets_mode` je uveden a není `hide` ani `disable`,
  5. stránka má klíč `filters`, ale žádnou dimenzi (chybí `dimensions`, nebo je prázdný).
- Každá zpráva je anglicky, ve stylu `krizky-map` (`"site.map.leaflet.js is not configured; map will not work"`), a obsahuje název stránky (klíč z `site.pages`). U případů 1–3 obsahuje i klíč dimenze. Příklad: `_log.warning("Filters on page '%s': dimension '%s' has unknown type '%s'; expected select, multiselect or text", page_name, dim_key, dim_type)`.
- Validace běží v hooku `extra_template_vars`. Core ho volá jednou za build (`krizky/site.py`, ř. ~177), kdežto `inject_head`/`inject_body_end`/`after_page_written` se volají pro každou stránku. Ve zbylých hoocích se varování nevypisují.
- Chování buildu se nemění. Vygenerované `page_filters`, filter config (`_build_filter_config`) i JSON jsou pro stejný vstup stejné jako dnes. Varování nic nezastaví ani nepřeskočí.
- `docs/configuration.md` obsahuje krátkou poznámku (česky), že plugin při chybné konfiguraci varuje v logu, a seznam kontrolovaných případů (pravidlo `docs/guidelines/docs-sync.md`).
- `scripts/verify` skončí s exit 0.

## Testy
TDD, nejdřív testy v `tests/test_filter_plugin.py`, pak implementace:
- Pro každý z případů 1–5 jeden test, který zavolá `FiltersPlugin().extra_template_vars(...)` s `caplog` (`caplog.set_level(logging.WARNING, logger="krizky_filters.plugin")`) a ověří, že v `caplog.records` je **právě jedno** varování a že jeho zpráva obsahuje název stránky (a u 1–3 i klíč dimenze).
- Test na platné konfiguraci: fixture `minimal_config` (případně i konfigurace z `test_extra_template_vars_text_dim`) neprodukuje žádné varování.
- Volitelně jednotkové testy čisté validační funkce (např. `_validate_filters(page_name, filters_cfg) -> list[str]` nebo podobné), pokud ji vyčleníš.

## Poznámky
- **Neplatný `sort` dnes padá.** `values._parse_sort` vyhodí `ValueError("Unknown sort field ...")` při volání `fetch_filter_values` (viz test `test_fetch_filter_values_sort_invalid_field`). To se nemění, spec říká, že chování buildu zůstane stejné. Validaci stránky proto spusť **před** výpočtem hodnot (`fetch_filter_values`), aby se varování vypsalo ještě před výjimkou. Test pro případ 3 pak obalí volání `pytest.raises(ValueError)` a zároveň ověří jedno varování v `caplog`. Pro kontrolu `sort` můžeš znovu použít `_SORT_ALIASES`/`_ALLOWED_SORT_FIELDS` z `values.py` (nebo zavolat `_parse_sort` v `try/except ValueError`). Neduplikuj seznam povolených polí.
- Dict `sort` bez klíče `order` je také neplatný tvar, varuj u něj.
- `sort` u dimenze `type: text` se nepoužívá, nevaliduj ho.
- Pokud je `filters:` v YAML prázdné (`None`), dnešní kód spadne na `None.get`. Tohle chování neměň a do rozsahu to nepatří. Případ 5 testuj na `filters: {}` a na `filters: {"dimensions": {}}`.
- U případu 2 neplatí jen chybějící klíč, ale i prázdný seznam (`search_fields: []`).
- Jedna stránka s více chybami vypíše více varování. Testy jednotlivých případů ale musí mít konfiguraci, kde vznikne právě jedno.
- Docstringy anglicky v Google stylu, žádné `from __future__ import annotations` (ruff TID251).

## Otázky
