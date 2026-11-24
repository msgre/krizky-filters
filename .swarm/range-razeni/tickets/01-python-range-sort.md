---
id: "01"
slug: python-range-sort
title: Python, šablony a dokumentace configu pro dimenzi range a sort_records
status: done
depends_on: []
files:
  - krizky_filters/plugin.py
  - krizky_filters/templates/_filter_widget_range.html
  - krizky_filters/templates/_filter_sort.html
  - krizky_filters/templates/_filter_widget.html
  - krizky_filters/assets/krizky-filters/filters.css
  - tests/test_filter_plugin.py
  - docs/configuration.md
  - docs/widgets.md
  - README.md
attempts: 2
pr: "12"
---

## Cíl
Celá Python a šablonová strana specifikace `.swarm/range-razeni/spec.md`: z části 1 odstavce „Konfigurace“ a „Python“ (dimenze `type: range`), z části 2 odstavce „Konfigurace“ a „Python“ (`sort_records`) a z části 4 dokumentace `docs/configuration.md`, `docs/widgets.md` a `README.md`. Chování ve `filters.js` (část 1 „JS“, část 2 „JS“, `docs/javascript.md`) řeší tikety 02 a 03, které běží souběžně a drží se stejného kontraktu ze specifikace (klíče `#filter-config` a hook atributy). Názvy klíčů a atributů proto musí přesně odpovídat specifikaci.

## Akceptační kritéria
Dimenze `range`:
- `_DIM_TYPES` obsahuje `range`. Varování o neznámém typu vyjmenuje `select, multiselect, text or range`.
- `extra_template_vars`: dimenze `range` má v `page_filters[page][dim]` přesně klíče `label`, `type: "range"`, `values: []`, `js_only: True`, `unit` a `step`. Pro `range` se nevolá `fetch_filter_values` ani `_resolve_url_template` a nepočítá se min a max.
- Výchozí hodnoty: `unit` = `""`, `step` = `"any"`. Stejné hodnoty jdou do `page_filters` i do `_build_filter_config`.
- `_build_filter_config`: dimenze `range` dostane přesně `{"label", "type": "range", "unit", "step"}` (bez `sort`, `many`, `searchFields`).
- Varování (jedno na každý problém, zpráva obsahuje název stránky, klíč dimenze a název klíče configu):
  - `range` s klíčem `many`, `sort` nebo `search_fields` (klíč se ignoruje),
  - `step`, které není kladné číslo (`0`, `-5`, `"abc"`, `True`) → varování a výchozí `"any"`. Explicitní `step: any` je platné a varování nemá.
  - `unit`, které není řetězec → varování a výchozí `""`.
- Nová šablona `krizky_filters/templates/_filter_widget_range.html` (vybírá ji `_filter_widget.html` podle `_dim.type`, ten se kvůli tomu nemění): dvě pole `<input type="number" inputmode="decimal" min="0">` s `data-filter-dimension="<dim>"` a `data-filter-range="min"` / `data-filter-range="max"`, popisky „od“ a „do“, `unit` za poli (jen když není prázdné) a atribut `step` z configu. Hodnoty do šablony jdou jen přes autoescape Jinja2 (žádné `|safe`).
- Obal dimenze `range` má `data-filter-js-only` (stávající mechanismus přes `js_only`). Stránka se `select` dimenzí s URL a `range` dimenzí: obal `[data-filter-widget]` atribut `data-filter-js-only` nemá.

`sort_records`:
- `extra_template_vars`: `page_filters[page]["_sort_records"] = {"param", "default_label", "options"}`, jen když má stránka `filters.sort_records`. Bez configu klíč `_sort_records` chybí. Výchozí `param` = `"sort"`, `default_label` = `"Výchozí řazení"`. `options` je seznam `{"field", "label"}`.
- `_build_filter_config` vrací vždy klíč `sortRecords`: `{"param": ..., "options": [{"field", "label"}, ...]}`, nebo `None` bez configu.
- Varování (log, build pokračuje, zpráva obsahuje název stránky):
  - `param` je stejný jako klíč některé dimenze,
  - `options` chybí nebo je prázdné,
  - položka `options` nemá `field` nebo `label` (taková položka se do `options` v `_sort_records` ani v `sortRecords` nedostane),
  - `filters.fields` je nastavené a neobsahuje `field` některé položky (položka zůstane).
- Nová šablona `krizky_filters/templates/_filter_sort.html`: obal s `data-filter-js-only`, v něm `<select data-filter-sort>` s první volbou `value=""` a textem `default_label` a pro každou položku dvě volby `value="<field>"` s textem „{label} ↑“ a `value="-<field>"` s textem „{label} ↓“. Texty šipek jsou v šabloně, aby šly přebít.
- `_filter_widget.html` vloží `{% include "_filter_sort.html" %}`, když `_dims._sort_records` existuje. Klíč `_sort_records` se nepovažuje za dimenzi (cyklus už přeskakuje klíče začínající `_`).
- Stávající testy (`select`, `multiselect`, `text`, JSON filtru, `inject_body_end`) projdou beze změny. `inject_body_end` se nemění.

Dokumentace (podle části 4 specifikace):
- `docs/configuration.md`: typ `range` (klíče `unit` a `step`, ignorované `many`/`sort`/`search_fields`, formát URL `?cena=3000000-5000000`, `?cena=3000000-`, `?cena=-5000000`, záznamy s `null` nebo bez pole při aktivním rozsahu neprojdou, fasety a placeholdery, jen nezáporná čísla, jen s JS), sekce `sort_records` (klíče, URL `?sort=cena` / `?sort=-cena`, výchozí řazení = `order_by` stránky, `null` a prázdné hodnoty na konci v obou směrech, `[data-filter-clear]` řazení nemaže) a seznam „Varování při chybné konfiguraci“ doplněný o všechna nová varování. Schema na začátku souboru obsahuje oba nové klíče.
- `docs/widgets.md`: šablony `_filter_widget_range.html` a `_filter_sort.html` v seznamu šablon, jejich hook atributy (`data-filter-range`, `data-filter-dimension`, `data-filter-sort`), přebití a umístění selectu jinam vlastním `{% include "_filter_sort.html" %}`. Tabulka kontextu `_dim` zná typ `range` a klíče `unit` a `step`.
- `README.md`: v „Klíčové vlastnosti“ rozsahový filtr a řazení výsledků, minimální ukázka configu s `type: range` a `sort_records`.
- `scripts/verify` skončí s exit 0.

## Testy
Nejdřív napiš selhávající testy v `tests/test_filter_plugin.py`, pak implementuj.
1. `page_filters` pro `range` přes `FiltersPlugin().extra_template_vars(...)` (vzor `test_extra_template_vars_text_dim`): s `unit` a `step` i bez nich (výchozí `""` a `"any"`).
2. `_build_filter_config` pro `range` s `unit`/`step` i bez nich (vzor `test_build_filter_config_text_dim`).
3. Varování pro `range` (`parametrize`): `many`, `sort`, `search_fields`, neplatné `step` (`0`, `-5`, `"abc"`), neplatné `unit` (číslo). Každý případ dá právě jedno varování s klíčem dimenze. Platná `range` dimenze (i se `step: any`) nedá žádné varování (vzor `_run_extra_vars`).
4. Vykreslení `_filter_widget.html` s `range` dimenzí (vzor `_render` a `_tag`): dvě pole s `data-filter-range="min"` a `"max"`, obě s `data-filter-dimension`, `step` a `min="0"`, obal dimenze s `data-filter-js-only`. Varianta se `select` dimenzí s URL: obal `[data-filter-widget]` atribut nemá.
5. `page_filters["_sort_records"]` a `sortRecords` s výchozím `param`/`default_label` i s vlastními. Bez `sort_records`: `_sort_records` chybí a `sortRecords` je `None`.
6. Každé varování `sort_records` (`parametrize`): kolize `param` s dimenzí, chybějící `options`, prázdné `options`, položka bez `field`, položka bez `label`, `field` mimo `filters.fields`. Platný config nedá žádné varování.
7. Vykreslení `_filter_widget.html` se `sort_records`: `<select data-filter-sort>` má výchozí volbu (`value=""`, text `default_label`) a 2 volby na položku (`cena`, `-cena`), obal selectu má `data-filter-js-only`. Bez `sort_records` select v HTML není.

## Poznámky
- Guidelines: `/Users/msgre/projects/muzeum/krizky/docs/guidelines/python.md` (žádné `from __future__ import annotations`, hlídá ruff TID251), `cross-language.md` (klíče `unit`, `step`, `sortRecords`, `param`, `options`, `field`, `label` přesně tak, protože je čte `filters.js` z tiketů 02 a 03), `docs-sync.md`, `security.md`.
- V `_warn_invalid_filters` musí větev pro `range` předběhnout stávající větev pro `sort`, jinak `sort` u `range` spadne do validace `sort` specu místo varování „nepoužije se“.
- `step` validuj jako `int`/`float` a ne `bool` (v Pythonu je `True` instancí `int`), hodnota > 0. Validaci dělej v jedné pomocné funkci, kterou použije `extra_template_vars` i `_build_filter_config`, ať se výchozí hodnoty nerozejdou.
- Validace `sort_records` patří do `_warn_invalid_filters`. Normalizaci (výchozí hodnoty a vyřazení položek bez `field`/`label`) dej do jedné pomocné funkce sdílené `extra_template_vars` a `_build_filter_config`.
- Když po vyřazení nezbude žádná položka, `_sort_records` a `sortRecords` přesto existují s prázdným `options`. Select pak má jen výchozí volbu. Nic dalšího nevymýšlej.
- `filters.css`: případně minimální styl pro rozsahová pole a select (nepovinné). Po úpravě spusť `npx --no-install prettier --write 'krizky_filters/assets/**/*.{js,css}'`.
- `filters.js` a `docs/javascript.md` neměň, patří tiketům 02 a 03.

## Otázky
